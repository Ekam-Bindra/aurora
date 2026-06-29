"""Risk genome service."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from aurora_db.models.commercial import Contract
from aurora_db.models.financial import Invoice
from aurora_db.models.org import Project, ProjectAssignment
from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import get_mart_rows
from aurora_ml.risk import RiskGenomeEngine, RiskOperationalContext
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .graph import graph_concentration, refresh_graph

_genome_cache: Dict[str, Dict[str, Any]] = {}
_history: Dict[str, List[Dict[str, Any]]] = {}
_genome_objects: Dict[str, Any] = {}


def _gather_context(session: Session, company_id: str) -> RiskOperationalContext:
    projects = session.execute(
        select(Project).where(Project.company_id == company_id)
    ).scalars().all()

    red_ratio = 0.0
    budget_var = 0.0
    if projects:
        red_count = sum(1 for p in projects if p.health == "red")
        red_ratio = red_count / len(projects)
        variances = []
        for p in projects:
            if p.budget_cents > 0:
                variances.append((p.spent_cents - p.budget_cents) / p.budget_cents)
        budget_var = sum(variances) / len(variances) if variances else 0.0

    invoice_stats = session.execute(
        select(Invoice.status, func.count())
        .where(Invoice.company_id == company_id)
        .group_by(Invoice.status)
    ).all()
    inv_counts = {status: int(cnt) for status, cnt in invoice_stats}
    total_inv = sum(inv_counts.values()) or 1
    overdue_ratio = inv_counts.get("overdue", 0) / total_inv

    today = date.today()
    horizon = today + timedelta(days=90)
    contracts = session.execute(
        select(Contract).where(Contract.company_id == company_id)
    ).scalars().all()
    expiring = 0
    expired_critical = 0
    for c in contracts:
        if c.end_date and today <= c.end_date <= horizon and c.status == "active":
            expiring += 1
        if c.status == "expired" and c.value_cents >= 500_000_00:
            expired_critical += 1

    assignments = session.execute(
        select(ProjectAssignment.allocation_pct)
        .where(ProjectAssignment.company_id == company_id)
    ).all()
    max_alloc = 0.0
    for (alloc,) in assignments:
        max_alloc = max(max_alloc, float(alloc or 0) / 100.0)

    conc = graph_concentration(company_id)
    vend_top = conc.get("vendors", {}).get("top_5_share", 0.0) or 0.0

    return RiskOperationalContext(
        red_project_ratio=red_ratio,
        budget_variance_pct=budget_var,
        dependency_centrality=min(1.0, vend_top * 1.2),
        overdue_ar_ratio=overdue_ratio,
        key_person_max_allocation=max_alloc,
        critical_open_roles=0,
        expiring_contracts=expiring,
        expired_critical_contracts=expired_critical,
        audit_findings=0,
        vendor_critical_spo=min(1.0, vend_top * 1.15),
        delivery_reliability=0.82 if vend_top > 0.35 else 0.90,
        attrition_rate=0.08 if max_alloc > 0.75 else 0.04,
    )


def compute_genome(session: Session, company_id: str) -> Dict[str, Any]:
    refresh_graph(session, company_id)
    rows = get_mart_rows(session, company_id)
    fin = FinancialEngine(rows)
    conc = graph_concentration(company_id)
    ctx = _gather_context(session, company_id)
    engine = RiskGenomeEngine(
        fin,
        customer_concentration=conc.get("customers"),
        vendor_concentration=conc.get("vendors"),
        context=ctx,
    )
    genome = engine.compute()
    payload = engine.to_dict(genome)
    _genome_cache[company_id] = payload
    _genome_objects[company_id] = (engine, genome)
    hist = _history.setdefault(company_id, [])
    hist.append(
        {
            "computed_at": payload["computed_at"],
            "overall_score": payload["overall_score"],
            "dimensions": {
                d["dimension"]: d["score"] for d in payload.get("dimensions", [])
            },
        }
    )
    if len(hist) > 52:
        _history[company_id] = hist[-52:]
    return payload


def get_genome(company_id: str) -> Optional[Dict[str, Any]]:
    return _genome_cache.get(company_id)


def get_dimension(company_id: str, dimension: str) -> Optional[Dict[str, Any]]:
    genome = _genome_cache.get(company_id)
    if not genome:
        return None
    for d in genome.get("dimensions", []):
        if d.get("dimension") == dimension:
            return d
    return None


def genome_history(company_id: str) -> List[Dict[str, Any]]:
    return list(_history.get(company_id, []))


def explain_risk_signal(company_id: str, signal_id: str) -> Optional[Dict[str, Any]]:
    stored = _genome_objects.get(company_id)
    if not stored:
        return None
    engine, genome = stored
    return engine.explain_dimension(genome, signal_id)
