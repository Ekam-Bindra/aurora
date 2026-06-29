"""Deterministic "Nimbus Retail Systems" demo generator + verification self-check.

Implements docs/data-model/demo-dataset-spec.md. Generation is seeded (default 42) and built
top-down so totals reconcile: a monthly revenue curve (trend x seasonal x noise) is allocated to
customers/products/invoices, with Pareto concentration and anomalies A-G planted analytically so
the §7.3 self-checks pass by construction. Seeding is idempotent and only ever touches the
``nimbus`` tenant.

The generator is **scalable** via ``scale`` (1.0 = full spec volumes) so tests can run a small,
fast dataset while CI/operations run the full-size set the §7.3 bands describe.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List

import numpy as np
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from ..models import (
    AppUser,
    Company,
    Contract,
    Customer,
    DataSource,
    Department,
    Employee,
    Expense,
    Invoice,
    InvoiceLineItem,
    Product,
    Project,
    ProjectAssignment,
    RevenueRecord,
    Role,
    UserRole,
    Vendor,
)
from ..types import new_uuid
from .personas import PERSONAS, ROLE_DEFINITIONS, hash_password

DEMO_SLUG = "nimbus"
MONTHS = 36
CRITICAL_VENDOR = "Vanguard Freight Co."
TOP_CUSTOMER = "Continental Mercantile Group"
KEY_PROJECT = "Key Account Fulfillment"
START_CASH = 6_500_000.0

# (name, code, headcount, annual_budget_usd)
DEPARTMENTS = [
    ("Executive", "EXEC", 8, 3_200_000),
    ("Finance", "FIN", 22, 3_000_000),
    ("Sales", "SALES", 90, 11_000_000),
    ("Marketing", "MKT", 35, 6_500_000),
    ("Operations", "OPS", 70, 7_000_000),
    ("Supply Chain", "SCM", 45, 5_500_000),
    ("Engineering", "ENG", 60, 9_000_000),
    ("Product", "PROD", 18, 3_000_000),
    ("Customer Support", "CS", 65, 4_500_000),
    ("Warehouse", "WH", 55, 4_000_000),
    ("HR / People", "HR", 12, 1_800_000),
    ("Legal & Compliance", "LEGAL", 10, 2_200_000),
]

# (line, n_skus, price_low_cents, price_high_cents, gross_margin)
PRODUCT_LINES = [
    ("Home & Living", 16, 2_000, 30_000, 0.42),
    ("Apparel", 14, 1_500, 15_000, 0.55),
    ("Electronics Accessories", 12, 1_000, 20_000, 0.30),
    ("Outdoor & Seasonal", 10, 2_500, 50_000, 0.48),
    ("Wholesale Bulk Goods", 8, 20_000, 500_000, 0.22),
]

SEASONAL = {
    1: 0.82, 2: 0.85, 3: 0.95, 4: 0.98, 5: 1.00, 6: 1.02,
    7: 0.98, 8: 1.02, 9: 1.05, 10: 1.18, 11: 1.45, 12: 1.55,
}

# Ground truth for the injected anomalies (also stored on company.settings).
ANOMALY_MANIFEST = [
    {"id": "A", "name": "Marketing expense spike", "month_index": 13, "magnitude": "+180%"},
    {"id": "B", "name": "Revenue dip", "month_index": 16, "magnitude": "-22%"},
    {"id": "C", "name": "Liquidity squeeze", "month_index": [19, 20, 21, 22, 23]},
    {"id": "D", "name": "Customer concentration creep", "month_index": list(range(24, 36))},
    {"id": "E", "name": "Vendor delivery slip", "month_index": 27, "entity": CRITICAL_VENDOR},
    {"id": "F", "name": "Margin erosion (Electronics)", "month_index": list(range(30, 36))},
    {"id": "G", "name": "Attrition cluster (Engineering)", "month_index": 31},
]

_FIRST_NAMES = [
    "Alex", "Bianca", "Chen", "Dmitri", "Elena", "Farah", "Grace", "Hassan", "Ines", "Jamal",
    "Kira", "Liam", "Maya", "Noah", "Olga", "Pedro", "Quinn", "Rosa", "Sven", "Tara",
    "Umar", "Vera", "WES", "Ximena", "Yuki", "Zane",
]
_LAST_NAMES = [
    "Adler", "Boone", "Cortez", "Davies", "Engel", "Fuentes", "Gallo", "Huang", "Ibrahim",
    "Jensen", "Kowalski", "Lopez", "Mbeki", "Novak", "Okafor", "Petrov", "Quist", "Romano",
    "Singh", "Tanaka", "Ueno", "Vargas", "Wong", "Xu", "Yamada", "Zito",
]
_BRAND_A = [
    "Summit", "Harbor", "Cedar", "Atlas", "Vertex", "Maple", "Orion", "Pioneer", "Beacon",
    "Granite", "Cobalt", "Meridian", "Aspen", "Falcon", "Lumen", "Ridge", "Onyx", "Vista",
]
_BRAND_B = [
    "Trading", "Wholesale", "Retail", "Goods", "Supply", "Mercantile", "Distributors",
    "Partners", "Group", "Markets", "Outfitters", "Logistics", "Brands", "Holdings",
]
_VENDOR_CATEGORIES = ["materials", "logistics", "saas", "marketing", "facilities", "services"]


@dataclass
class CheckResult:
    name: str
    expected: str
    actual: str
    passed: bool


def _add_months(d: date, n: int) -> date:
    total = (d.year * 12 + (d.month - 1)) + n
    return date(total // 12, total % 12 + 1, 1)


def _month_axis() -> List[date]:
    start = _add_months(date.today().replace(day=1), -(MONTHS - 1))
    return [_add_months(start, i) for i in range(MONTHS)]


def _allocate_counts(total: int, weights) -> np.ndarray:
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    raw = weights * total
    base = np.floor(raw).astype(int)
    remainder = int(total - base.sum())
    if remainder > 0:
        for idx in np.argsort(-(raw - base))[:remainder]:
            base[idx] += 1
    return base


def _bulk_insert(session: Session, model, rows: List[dict], chunk: int = 1000) -> None:
    for start in range(0, len(rows), chunk):
        session.execute(insert(model), rows[start : start + chunk])


def _wipe_company(session: Session, company_id: str) -> None:
    # FK ON DELETE CASCADE (PostgreSQL native; SQLite via PRAGMA in make_engine) removes all
    # tenant-scoped rows. Only the nimbus tenant is affected.
    session.execute(delete(Company).where(Company.id == company_id))
    session.flush()


def seed_nimbus(
    session: Session,
    *,
    seed: int = 42,
    scale: float = 1.0,
    password: str = "aurora-demo-2026",
    force: bool = True,
) -> dict:
    """Idempotently (re)create the Nimbus demo tenant. Returns a summary incl. persona logins."""
    rng = np.random.default_rng(seed)
    logins = [(email, role) for _, email, _, role in PERSONAS]

    existing = session.scalars(select(Company).where(Company.slug == DEMO_SLUG)).first()
    if existing is not None and not force:
        return {"company_id": existing.id, "created": False, "logins": logins}
    if existing is not None:
        _wipe_company(session, existing.id)

    months = _month_axis()
    n_customers = max(12, round(300 * scale))
    n_vendors = max(6, round(80 * scale))
    target_employees = max(40, round(500 * scale))
    total_invoices = max(200, round(20_000 * scale))

    # ── 1. Company, roles, persona users ────────────────────────────────
    company = Company(
        name="Nimbus Retail Systems",
        slug=DEMO_SLUG,
        industry="Omnichannel retail & B2B wholesale",
        base_currency="USD",
        fiscal_year_start_month=1,
        settings={"seed": seed, "scale": scale, "anomalies": ANOMALY_MANIFEST},
    )
    session.add(company)
    session.flush()
    cid = company.id

    role_ids: Dict[str, str] = {}
    for name, defn in ROLE_DEFINITIONS.items():
        role = Role(
            company_id=cid,
            name=name,
            description=defn["description"],
            permissions=defn["permissions"],
            is_system=True,
        )
        session.add(role)
        session.flush()
        role_ids[name] = role.id

    pw_hash = hash_password(password)
    for full_name, email, title, role_name in PERSONAS:
        user = AppUser(
            company_id=cid,
            email=email.lower(),
            full_name=full_name,
            title=title,
            password_hash=pw_hash,
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.add(
            UserRole(
                company_id=cid, user_id=user.id, role_id=role_ids[role_name], scope_type="tenant"
            )
        )

    # ── 2. Departments & employees ──────────────────────────────────────
    dept_ids: Dict[str, str] = {}
    for name, code, _hc, budget in DEPARTMENTS:
        dept = Department(
            company_id=cid, name=name, code=code, annual_budget_cents=budget * 100
        )
        session.add(dept)
        session.flush()
        dept_ids[code] = dept.id

    headcounts = np.array([d[2] for d in DEPARTMENTS], dtype=float)
    emp_counts = _allocate_counts(target_employees, headcounts)
    tier_bands = [
        ("Associate", 55_000, 120_000, 0.62),
        ("Manager", 120_000, 180_000, 0.23),
        ("Director", 180_000, 260_000, 0.10),
        ("VP", 260_000, 500_000, 0.05),
    ]
    tier_p = np.array([b[3] for b in tier_bands])
    tier_p = tier_p / tier_p.sum()

    emp_rows: List[dict] = []
    dept_payroll_annual: Dict[str, int] = {code: 0 for _, code, _, _ in DEPARTMENTS}
    dept_first_emp: Dict[str, str] = {}
    key_engineer_ids: List[str] = []

    for di, (_name, code, _hc, _budget) in enumerate(DEPARTMENTS):
        for _ in range(int(emp_counts[di])):
            tier_idx = int(rng.choice(len(tier_bands), p=tier_p))
            tname, lo, hi, _ = tier_bands[tier_idx]
            salary = int(rng.integers(lo, hi))
            etype = str(rng.choice(["full_time", "contractor", "part_time"], p=[0.85, 0.10, 0.05]))
            hire = months[0] - timedelta(days=int(rng.integers(0, 365 * 5)))
            terminated = rng.random() < 0.06
            term_date = None
            status = "active"
            if terminated:
                term_date = months[0] + timedelta(days=int(rng.integers(0, 365 * 3)))
                status = "terminated"
            emp_id = new_uuid()
            emp_rows.append(
                {
                    "id": emp_id,
                    "company_id": cid,
                    "department_id": dept_ids[code],
                    "full_name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
                    "title": f"{tname} ({code})",
                    "employment_type": etype,
                    "annual_salary_cents": salary * 100,
                    "currency": "USD",
                    "hire_date": hire,
                    "termination_date": term_date,
                    "status": status,
                }
            )
            dept_payroll_annual[code] += salary
            dept_first_emp.setdefault(code, emp_id)

    # Anomaly G + key-person dependency: 3 Engineering leads, >80% on the key project,
    # all departing in month 32.
    for _ in range(3):
        emp_id = new_uuid()
        key_engineer_ids.append(emp_id)
        emp_rows.append(
            {
                "id": emp_id,
                "company_id": cid,
                "department_id": dept_ids["ENG"],
                "full_name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
                "title": "Principal Engineer (ENG)",
                "employment_type": "full_time",
                "annual_salary_cents": 245_000 * 100,
                "currency": "USD",
                "hire_date": months[0] - timedelta(days=int(rng.integers(365 * 2, 365 * 5))),
                "termination_date": months[31] + timedelta(days=10),
                "status": "terminated",
            }
        )
        dept_payroll_annual["ENG"] += 245_000

    _bulk_insert(session, Employee, emp_rows)
    for code, emp_id in dept_first_emp.items():
        session.execute(
            update(Department)
            .where(Department.id == dept_ids[code])
            .values(head_employee_id=emp_id)
        )

    # ── 3. Customers (Pareto revenue weights) ───────────────────────────
    cust_ids: List[str] = []
    cust_rows: List[dict] = []
    for i in range(n_customers):
        if i == 0:
            name, segment, status = TOP_CUSTOMER, "enterprise", "active"
        else:
            name = f"{rng.choice(_BRAND_A)} {rng.choice(_BRAND_B)}"
            segment = str(rng.choice(["enterprise", "smb", "retail"], p=[0.13, 0.70, 0.17]))
            status = str(rng.choice(["active", "churned", "prospect"], p=[0.83, 0.12, 0.05]))
        region = str(rng.choice(["NA", "EU", "APAC"], p=[0.60, 0.25, 0.15]))
        cust_id = new_uuid()
        cust_ids.append(cust_id)
        cust_rows.append(
            {
                "id": cust_id,
                "company_id": cid,
                "name": name,
                "segment": segment,
                "region": region,
                "status": status,
            }
        )
    _bulk_insert(session, Customer, cust_rows)

    # Non-top customer weights (Pareto), normalized to sum 1.
    ranks = np.arange(1, n_customers)
    cust_w = 1.0 / (ranks + 0.5) ** 1.1
    cust_w = cust_w / cust_w.sum()
    # Monthly top-customer share with creep (anomaly D): ~11% early -> ~13.5% recent year.
    top_share = np.empty(MONTHS)
    top_share[:24] = 0.11
    top_share[24:] = np.linspace(0.12, 0.155, MONTHS - 24)

    # ── 4. Vendors (Pareto spend weights; top-5 == 40%) ─────────────────
    vend_ids: List[str] = []
    vend_rows: List[dict] = []
    for i in range(n_vendors):
        if i == 0:
            name, category, criticality = CRITICAL_VENDOR, "logistics", "critical"
        else:
            name = f"{rng.choice(_BRAND_A)} {rng.choice(_VENDOR_CATEGORIES).title()} Co."
            category = str(rng.choice(_VENDOR_CATEGORIES))
            criticality = str(rng.choice(["standard", "low"], p=[0.8, 0.2]))
        vend_id = new_uuid()
        vend_ids.append(vend_id)
        vend_rows.append(
            {
                "id": vend_id,
                "company_id": cid,
                "name": name,
                "category": category,
                "criticality": criticality,
                "status": "active",
            }
        )
    _bulk_insert(session, Vendor, vend_rows)

    vend_w = np.zeros(n_vendors)
    head = np.array([0.12, 0.10, 0.08, 0.06, 0.04])  # top-5 share == 0.40, strictly decreasing
    if n_vendors > 5:
        vend_w[:5] = head
        # Tail strictly below head's minimum so the top-5 are always the 5 largest by spend
        # (holds for the spec's 80 vendors; tiny scaled datasets skip this check in verify()).
        tail = np.linspace(0.039, 0.001, n_vendors - 5)
        vend_w[5:] = tail / tail.sum() * 0.60
    elif n_vendors == 5:
        vend_w[:] = head
    else:
        vend_w[:] = 1.0 / n_vendors
    vendor_categories = [r["category"] for r in vend_rows]

    # ── 5. Products ─────────────────────────────────────────────────────
    prod_rows: List[dict] = []
    products_all: List[str] = []
    for line, n_sku, plo, phi, margin in PRODUCT_LINES:
        n = max(2, round(n_sku * scale)) if scale < 1 else n_sku
        code = "".join(w[0] for w in line.split())[:4].upper()
        for s in range(n):
            price = int(rng.integers(plo, phi))
            cost = int(round(price * (1 - margin)))
            pid = new_uuid()
            products_all.append(pid)
            prod_rows.append(
                {
                    "id": pid,
                    "company_id": cid,
                    "name": f"{line} {s + 1:02d}",
                    "sku": f"{code}-{s + 1:03d}",
                    "line": line,
                    "unit_price_cents": price,
                    "unit_cost_cents": cost,
                    "currency": "USD",
                    "status": "active",
                }
            )
    _bulk_insert(session, Product, prod_rows)

    # ── 6. Financial engine: monthly revenue & COGS curves ──────────────
    monthly_growth = 1.18 ** (1 / 12)
    base = 3_000_000.0
    revenue = np.empty(MONTHS)
    for m in range(MONTHS):
        noise = float(np.clip(rng.normal(1.0, 0.04), 0.85, 1.15))
        revenue[m] = base * (monthly_growth**m) * SEASONAL[months[m].month] * noise
    revenue[16] *= 1.0 - 0.22  # anomaly B: revenue dip

    gross_margin = np.linspace(0.39, 0.42, MONTHS)
    cogs = revenue * (1.0 - gross_margin)
    elec_share = 0.28
    for m in range(30, MONTHS):  # anomaly F: electronics input inflation -> COGS up
        cogs[m] += revenue[m] * elec_share * 0.70 * 0.12

    # ── 7. Revenue records (customer x month) ───────────────────────────
    rr_rows: List[dict] = []
    for m in range(MONTHS):
        pm = months[m]
        rr_rows.append(
            {
                "id": new_uuid(),
                "company_id": cid,
                "customer_id": cust_ids[0],
                "period_month": pm,
                "amount_cents": int(round(revenue[m] * top_share[m] * 100)),
                "recognition_type": "point",
                "currency": "USD",
            }
        )
        remainder = revenue[m] * (1.0 - top_share[m])
        for k in range(1, n_customers):
            amount = int(round(remainder * cust_w[k - 1] * 100))
            if amount <= 0:
                continue
            rr_rows.append(
                {
                    "id": new_uuid(),
                    "company_id": cid,
                    "customer_id": cust_ids[k],
                    "period_month": pm,
                    "amount_cents": amount,
                    "recognition_type": "point",
                    "currency": "USD",
                }
            )
    _bulk_insert(session, RevenueRecord, rr_rows)

    # ── 8. Invoices + line items (~total_invoices, seasonality-weighted) ─
    inv_counts = _allocate_counts(total_invoices, revenue / revenue.sum())
    inv_rows: List[dict] = []
    li_rows: List[dict] = []
    invoice_no = 0
    for m in range(MONTHS):
        count = int(inv_counts[m])
        if count <= 0:
            continue
        pm = months[m]
        probs = np.empty(n_customers)
        probs[0] = top_share[m]
        probs[1:] = (1.0 - top_share[m]) * cust_w
        probs = probs / probs.sum()
        choices = rng.choice(n_customers, size=count, p=probs)
        jitter = np.clip(rng.normal(1.0, 0.25, count), 0.3, 3.0)
        totals = revenue[m] * 100 * jitter / jitter.sum()
        statuses = rng.choice(
            ["paid", "issued", "overdue", "void"], size=count, p=[0.80, 0.12, 0.05, 0.03]
        )
        for i in range(count):
            invoice_no += 1
            total_c = int(round(totals[i]))
            subtotal = int(round(total_c / 1.08))
            tax = total_c - subtotal
            issue = date(pm.year, pm.month, int(rng.integers(1, 28)))
            status = str(statuses[i])
            paid = (
                issue + timedelta(days=int(rng.choice([30, 45, 60])))
                if status == "paid"
                else None
            )
            iid = new_uuid()
            inv_rows.append(
                {
                    "id": iid,
                    "company_id": cid,
                    "customer_id": cust_ids[int(choices[i])],
                    "invoice_number": f"INV-{invoice_no:06d}",
                    "issue_date": issue,
                    "due_date": issue + timedelta(days=30),
                    "paid_date": paid,
                    "subtotal_cents": subtotal,
                    "tax_cents": tax,
                    "total_cents": total_c,
                    "currency": "USD",
                    "status": status,
                }
            )
            n_li = int(rng.integers(1, 7))
            parts = np.clip(rng.normal(1.0, 0.3, n_li), 0.2, 3.0)
            parts = parts / parts.sum() * subtotal
            for li in range(n_li):
                pid = products_all[int(rng.integers(0, len(products_all)))]
                amount = int(round(parts[li]))
                qty = int(rng.integers(1, 5))
                unit = max(1, int(round(amount / qty)))
                li_rows.append(
                    {
                        "id": new_uuid(),
                        "company_id": cid,
                        "invoice_id": iid,
                        "product_id": pid,
                        "quantity": Decimal(qty),
                        "unit_price_cents": unit,
                        "amount_cents": amount,
                    }
                )
    _bulk_insert(session, Invoice, inv_rows)
    _bulk_insert(session, InvoiceLineItem, li_rows)

    # ── 9. Expenses: vendor-attributed (COGS + opex), payroll, marketing ─
    exp_rows: List[dict] = []
    vendor_opex_ratio = 0.12
    for m in range(MONTHS):
        pm = months[m]
        cogs_m = float(cogs[m])
        vop_m = revenue[m] * vendor_opex_ratio
        spend_m = cogs_m + vop_m
        cogs_frac = cogs_m / spend_m if spend_m > 0 else 0.0
        for vi in range(n_vendors):
            v_total = spend_m * vend_w[vi]
            c_part = v_total * cogs_frac
            o_part = v_total - c_part
            if c_part > 0:
                exp_rows.append(
                    {
                        "id": new_uuid(), "company_id": cid, "vendor_id": vend_ids[vi],
                        "department_id": dept_ids["SCM"], "category": "cogs",
                        "amount_cents": int(round(c_part * 100)), "currency": "USD",
                        "expense_date": pm, "is_recurring": False,
                    }
                )
            if o_part > 0:
                exp_rows.append(
                    {
                        "id": new_uuid(), "company_id": cid, "vendor_id": vend_ids[vi],
                        "department_id": dept_ids["SCM"], "category": vendor_categories[vi],
                        "amount_cents": int(round(o_part * 100)), "currency": "USD",
                        "expense_date": pm, "is_recurring": True,
                    }
                )
        for code, annual in dept_payroll_annual.items():
            exp_rows.append(
                {
                    "id": new_uuid(), "company_id": cid, "department_id": dept_ids[code],
                    "category": "payroll", "amount_cents": int(round(annual / 12 * 100)),
                    "currency": "USD", "expense_date": pm, "is_recurring": True,
                }
            )
        marketing = revenue[m] * 0.06
        if m == 13:  # anomaly A
            marketing *= 2.8
        exp_rows.append(
            {
                "id": new_uuid(), "company_id": cid, "department_id": dept_ids["MKT"],
                "category": "marketing", "amount_cents": int(round(marketing * 100)),
                "currency": "USD", "expense_date": pm, "is_recurring": False,
            }
        )
        for cat, amt in (("rent", 120_000), ("facilities", 60_000)):
            exp_rows.append(
                {
                    "id": new_uuid(), "company_id": cid, "category": cat,
                    "amount_cents": amt * 100, "currency": "USD",
                    "expense_date": pm, "is_recurring": True,
                }
            )
        if 19 <= m <= 23:  # anomaly C: liquidity squeeze (one-time disbursements)
            exp_rows.append(
                {
                    "id": new_uuid(), "company_id": cid, "category": "one_time",
                    "amount_cents": int(round(revenue[m] * 0.55 * 100)), "currency": "USD",
                    "expense_date": pm, "is_recurring": False,
                }
            )
    _bulk_insert(session, Expense, exp_rows)

    # ── 10. Projects, assignments (dependency chain), contracts, sources ─
    proj_rows: List[dict] = []
    key_pid = new_uuid()
    proj_rows.append(
        {
            "id": key_pid, "company_id": cid, "department_id": dept_ids["OPS"],
            "customer_id": cust_ids[0], "name": KEY_PROJECT, "status": "active",
            "budget_cents": 4_000_000 * 100, "spent_cents": 4_600_000 * 100, "health": "red",
        }
    )
    for i in range(max(4, round(25 * scale)) - 1):
        budget = int(rng.integers(200_000, 3_000_000))
        spent = int(budget * float(rng.uniform(0.4, 1.4)))
        ratio = spent / budget
        health = "red" if ratio > 1.05 else ("amber" if ratio > 0.9 else "green")
        proj_rows.append(
            {
                "id": new_uuid(), "company_id": cid,
                "department_id": dept_ids[str(rng.choice(list(dept_ids.keys())))],
                "name": f"Initiative {i + 1:02d}", "status": "active",
                "budget_cents": budget * 100, "spent_cents": spent * 100, "health": health,
            }
        )
    _bulk_insert(session, Project, proj_rows)

    pa_rows = [
        {
            "id": new_uuid(), "company_id": cid, "project_id": key_pid,
            "employee_id": eid, "allocation_pct": Decimal(int(rng.integers(82, 96))),
            "role_on_project": "Lead Engineer",
        }
        for eid in key_engineer_ids
    ]
    _bulk_insert(session, ProjectAssignment, pa_rows)

    con_rows: List[dict] = [
        {
            "id": new_uuid(), "company_id": cid, "party_type": "customer",
            "customer_id": cust_ids[0], "title": "Master Supply Agreement",
            "value_cents": 12_000_000 * 100, "currency": "USD", "renewal_type": "auto",
            "status": "active",
        },
        {
            "id": new_uuid(), "company_id": cid, "party_type": "vendor",
            "vendor_id": vend_ids[0], "title": "Logistics MSA (critical)",
            "value_cents": 6_000_000 * 100, "currency": "USD", "renewal_type": "manual",
            "status": "active",
        },
    ]
    for i in range(max(2, round(120 * scale))):
        con_rows.append(
            {
                "id": new_uuid(), "company_id": cid, "party_type": "customer",
                "customer_id": cust_ids[int(rng.integers(0, n_customers))],
                "title": f"Customer Contract {i + 1:03d}",
                "value_cents": int(rng.integers(50_000, 2_000_000)) * 100, "currency": "USD",
                "renewal_type": str(rng.choice(["auto", "manual", "none"])),
                "status": str(rng.choice(["active", "expired"], p=[0.85, 0.15])),
            }
        )
    for i in range(max(1, round(50 * scale))):
        con_rows.append(
            {
                "id": new_uuid(), "company_id": cid, "party_type": "vendor",
                "vendor_id": vend_ids[int(rng.integers(0, n_vendors))],
                "title": f"Vendor Contract {i + 1:03d}",
                "value_cents": int(rng.integers(50_000, 1_500_000)) * 100, "currency": "USD",
                "renewal_type": str(rng.choice(["auto", "manual", "none"])),
                "status": str(rng.choice(["active", "expired"], p=[0.85, 0.15])),
            }
        )
    _bulk_insert(session, Contract, con_rows)

    _bulk_insert(
        session,
        DataSource,
        [
            {"id": new_uuid(), "company_id": cid, "kind": "accounting",
             "name": "QuickBooks (demo)", "config": {}, "status": "connected"},
            {"id": new_uuid(), "company_id": cid, "kind": "file",
             "name": "Manual CSV uploads", "config": {}, "status": "connected"},
        ],
    )

    session.flush()
    return {
        "company_id": cid,
        "created": True,
        "logins": logins,
        "counts": {
            "departments": len(DEPARTMENTS),
            "employees": len(emp_rows),
            "customers": n_customers,
            "vendors": n_vendors,
            "products": len(prod_rows),
            "invoices": len(inv_rows),
            "revenue_records": len(rr_rows),
            "expenses": len(exp_rows),
        },
    }


def _recent_year_bounds(session: Session, cid: str):
    max_period = session.scalar(
        select(func.max(RevenueRecord.period_month)).where(RevenueRecord.company_id == cid)
    )
    if max_period is None:
        return None, None
    recent_start = _add_months(max_period.replace(day=1), -11)
    return recent_start, max_period


def verify(session: Session, company_id: str, *, full: bool = True) -> List[CheckResult]:
    """Run the §7.3 self-checks. ``full`` adds the absolute-volume bands (full-scale only)."""
    cid = company_id
    checks: List[CheckResult] = []

    def add(name, expected, actual, passed):
        checks.append(CheckResult(name, str(expected), str(actual), bool(passed)))

    def count(model):
        return int(
            session.scalar(
                select(func.count()).select_from(model).where(model.company_id == cid)
            )
            or 0
        )

    recent_start, max_period = _recent_year_bounds(session, cid)
    n_months = int(
        session.scalar(
            select(func.count(func.distinct(RevenueRecord.period_month))).where(
                RevenueRecord.company_id == cid
            )
        )
        or 0
    )
    add("Months of financials", "== 36", n_months, n_months == 36)

    # Recent-year revenue & gross margin.
    rev_recent = float(
        session.scalar(
            select(func.coalesce(func.sum(RevenueRecord.amount_cents), 0)).where(
                RevenueRecord.company_id == cid, RevenueRecord.period_month >= recent_start
            )
        )
        or 0
    ) / 100.0
    cogs_recent = float(
        session.scalar(
            select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(
                Expense.company_id == cid,
                Expense.category == "cogs",
                Expense.expense_date >= recent_start,
            )
        )
        or 0
    ) / 100.0
    gm_recent = (1.0 - cogs_recent / rev_recent) if rev_recent else 0.0
    add("Blended gross margin (recent yr)", "39%-43%", f"{gm_recent * 100:.1f}%",
        0.39 <= gm_recent <= 0.43)

    # Top customer revenue share (recent year).
    top_cust_amt = float(
        session.scalar(
            select(func.coalesce(func.sum(RevenueRecord.amount_cents), 0))
            .join(Customer, Customer.id == RevenueRecord.customer_id)
            .where(
                RevenueRecord.company_id == cid,
                RevenueRecord.period_month >= recent_start,
                Customer.name == TOP_CUSTOMER,
            )
        )
        or 0
    )
    top_share_val = (top_cust_amt / 100.0 / rev_recent) if rev_recent else 0.0
    add("Top customer revenue share", "13%-15%", f"{top_share_val * 100:.1f}%",
        0.13 <= top_share_val <= 0.15)

    # Top-5 vendor spend share (all vendor-attributed expense). Only structurally meaningful
    # with enough vendors (the spec's 80); skipped for tiny scaled datasets.
    vendor_spend = session.execute(
        select(Expense.vendor_id, func.sum(Expense.amount_cents))
        .where(Expense.company_id == cid, Expense.vendor_id.isnot(None))
        .group_by(Expense.vendor_id)
    ).all()
    if full or len(vendor_spend) >= 40:
        total_vendor_spend = sum(float(v) for _, v in vendor_spend) or 1.0
        top5 = sum(sorted((float(v) for _, v in vendor_spend), reverse=True)[:5])
        top5_share = top5 / total_vendor_spend
        add("Top-5 vendor spend share", "38%-42%", f"{top5_share * 100:.1f}%",
            0.38 <= top5_share <= 0.42)

    # Anomaly A — marketing spike at month index 13. Aggregate by month: "marketing" is also a
    # vendor opex category, so there are several marketing rows per month that must be summed.
    mkt = session.execute(
        select(Expense.expense_date, func.sum(Expense.amount_cents))
        .where(Expense.company_id == cid, Expense.category == "marketing")
        .group_by(Expense.expense_date)
        .order_by(Expense.expense_date)
    ).all()
    mkt_vals = [float(a) for _, a in mkt]
    # Compare the spike month to its nearest non-spike neighbors rather than the global
    # median: marketing tracks a growing revenue trend, so a global median understates the
    # early-period baseline. A genuine spike must stand out against adjacent months.
    a_ok = False
    if len(mkt_vals) >= 16:
        neighbors = [mkt_vals[11], mkt_vals[12], mkt_vals[14], mkt_vals[15]]
        a_ok = mkt_vals[13] > 2.0 * (sum(neighbors) / len(neighbors))
    add("Anomaly A (marketing spike)", "present", "present" if a_ok else "missing", a_ok)

    # Anomaly B — revenue dip at month index 16 vs neighbors.
    rev_by_month = [
        float(v)
        for v in session.scalars(
            select(func.sum(RevenueRecord.amount_cents))
            .where(RevenueRecord.company_id == cid)
            .group_by(RevenueRecord.period_month)
            .order_by(RevenueRecord.period_month)
        ).all()
    ]
    b_ok = (
        len(rev_by_month) >= 18
        and rev_by_month[16] < 0.85 * ((rev_by_month[15] + rev_by_month[17]) / 2.0)
    )
    add("Anomaly B (revenue dip)", "present", "present" if b_ok else "missing", b_ok)

    # Anomaly C — liquidity squeeze: runway dips in months 20-24 vs month 12.
    exp_by_month = {
        d: float(v)
        for d, v in session.execute(
            select(Expense.expense_date, func.sum(Expense.amount_cents))
            .where(Expense.company_id == cid)
            .group_by(Expense.expense_date)
            .order_by(Expense.expense_date)
        ).all()
    }
    months_sorted = sorted(exp_by_month.keys())
    runway = []
    cash = START_CASH
    disb_series = [exp_by_month[d] / 100.0 for d in months_sorted]
    coll_series = rev_by_month  # cash-basis approximation
    for i, _d in enumerate(months_sorted):
        coll = coll_series[i] / 100.0 if i < len(coll_series) else 0.0
        cash += coll - disb_series[i]
        trailing = np.mean(disb_series[max(0, i - 2) : i + 1]) or 1.0
        runway.append(cash / trailing)
    c_ok = (
        len(runway) >= 24
        and min(runway[19:24]) < 0.7 * runway[11]
    )
    add("Anomaly C (liquidity squeeze)", "present", "present" if c_ok else "missing", c_ok)

    # Anomaly D — concentration creep: recent share > early share.
    early_start = months_sorted[0] if months_sorted else recent_start
    early_total = float(
        session.scalar(
            select(func.coalesce(func.sum(RevenueRecord.amount_cents), 0)).where(
                RevenueRecord.company_id == cid,
                RevenueRecord.period_month < _add_months(early_start, 12),
            )
        ) or 0
    )
    early_top = float(
        session.scalar(
            select(func.coalesce(func.sum(RevenueRecord.amount_cents), 0))
            .join(Customer, Customer.id == RevenueRecord.customer_id)
            .where(
                RevenueRecord.company_id == cid,
                RevenueRecord.period_month < _add_months(early_start, 12),
                Customer.name == TOP_CUSTOMER,
            )
        ) or 0
    )
    early_share = (early_top / early_total) if early_total else 0.0
    d_ok = top_share_val > early_share + 0.01
    add("Anomaly D (concentration creep)", "recent > early",
        f"{early_share * 100:.1f}% -> {top_share_val * 100:.1f}%", d_ok)

    # Anomaly E — critical vendor present.
    crit = session.scalar(
        select(func.count()).select_from(Vendor).where(
            Vendor.company_id == cid, Vendor.name == CRITICAL_VENDOR,
            Vendor.criticality == "critical",
        )
    )
    add("Anomaly E (critical vendor)", "present", "present" if crit else "missing", bool(crit))

    # Anomaly F — gross margin erosion (late months < mid months).
    cogs_by_month = [
        float(v)
        for v in session.scalars(
            select(func.sum(Expense.amount_cents))
            .where(Expense.company_id == cid, Expense.category == "cogs")
            .group_by(Expense.expense_date)
            .order_by(Expense.expense_date)
        ).all()
    ]
    f_ok = False
    if len(rev_by_month) >= 36 and len(cogs_by_month) >= 36:
        gm_mid = 1.0 - sum(cogs_by_month[27:30]) / sum(rev_by_month[27:30])
        gm_late = 1.0 - sum(cogs_by_month[33:36]) / sum(rev_by_month[33:36])
        f_ok = gm_late < gm_mid
    add("Anomaly F (margin erosion)", "late < mid", "present" if f_ok else "missing", f_ok)

    # Anomaly G — 3 Engineering departures clustered in month 32.
    g_count = 0
    if len(months_sorted) >= 32:
        g_dept = session.scalar(
            select(Department.id).where(Department.company_id == cid, Department.code == "ENG")
        )
        g_count = int(
            session.scalar(
                select(func.count()).select_from(Employee).where(
                    Employee.company_id == cid,
                    Employee.department_id == g_dept,
                    Employee.status == "terminated",
                    Employee.termination_date >= months_sorted[31],
                )
            )
            or 0
        )
    add("Anomaly G (attrition cluster)", ">= 3", g_count, g_count >= 3)

    # Dependency chain (relational backbone of the knowledge graph).
    key_proj = session.scalar(
        select(Project.id)
        .join(Customer, Customer.id == Project.customer_id)
        .where(
            Project.company_id == cid,
            Project.name == KEY_PROJECT,
            Customer.name == TOP_CUSTOMER,
        )
    )
    chain_assignments = 0
    if key_proj:
        chain_assignments = int(
            session.scalar(
                select(func.count()).select_from(ProjectAssignment).where(
                    ProjectAssignment.company_id == cid,
                    ProjectAssignment.project_id == key_proj,
                    ProjectAssignment.allocation_pct > 80,
                )
            )
            or 0
        )
    chain_ok = bool(key_proj) and chain_assignments >= 3 and bool(crit)
    add("Dependency chain (§6)", "present", "present" if chain_ok else "missing", chain_ok)

    if full:
        add("Departments", "== 12", count(Department), count(Department) == 12)
        emp = count(Employee)
        add("Employees", "480-520", emp, 480 <= emp <= 520)
        cu, ve = count(Customer), count(Vendor)
        add("Customers", "== 300", cu, cu == 300)
        add("Vendors", "== 80", ve, ve == 80)
        pr = count(Product)
        add("Product SKUs", "55-65", pr, 55 <= pr <= 65)
        inv = count(Invoice)
        add("Invoices", "19000-21000", inv, 19_000 <= inv <= 21_000)
        add("Recent-year revenue", "$45M-$62M", f"${rev_recent / 1e6:.1f}M",
            45e6 <= rev_recent <= 62e6)

    return checks


def all_passed(checks: List[CheckResult]) -> bool:
    return all(c.passed for c in checks)
