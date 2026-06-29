"""Build a tenant graph snapshot from canonical SQLAlchemy data."""

from __future__ import annotations

from datetime import date

from aurora_db.models import (
    Company,
    Contract,
    Customer,
    Department,
    Employee,
    Expense,
    Invoice,
    InvoiceLineItem,
    Product,
    Project,
    ProjectAssignment,
    RevenueRecord,
    Vendor,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurora_graph.types import GraphEdge, GraphNode, GraphSnapshot

CRITICAL_VENDOR = "Vanguard Freight Co."
ELECTRONICS_LINE = "Electronics Accessories"
SCM_CODE = "SCM"


def sync_company_graph(session: Session, company_id: str) -> GraphSnapshot:
    """Project relational truth into an in-memory graph for traversal."""
    company = session.get(Company, company_id)
    if company is None:
        return GraphSnapshot(tenant_id=company_id)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    def add_node(node_id: str, label: str, name: str, **props) -> str:
        nodes.append(GraphNode(id=node_id, label=label, name=name, properties=dict(props)))
        return node_id

    add_node(company_id, "Company", company.name, industry=company.industry)

    dept_rows = session.execute(
        select(Department).where(Department.company_id == company_id)
    ).scalars().all()
    dept_by_id = {d.id: d for d in dept_rows}
    for d in dept_rows:
        add_node(d.id, "Department", d.name, code=d.code)
        edges.append(GraphEdge(company_id, d.id, "HAS_DEPARTMENT"))

    emp_rows = session.execute(
        select(Employee).where(Employee.company_id == company_id)
    ).scalars().all()
    for e in emp_rows:
        add_node(e.id, "Employee", e.full_name, title=e.title, status=e.status)
        if e.department_id and e.department_id in dept_by_id:
            edges.append(GraphEdge(e.department_id, e.id, "EMPLOYS"))

    cust_rows = session.execute(
        select(Customer).where(Customer.company_id == company_id)
    ).scalars().all()
    cust_by_id = {c.id: c for c in cust_rows}
    for c in cust_rows:
        add_node(c.id, "Customer", c.name, segment=c.segment, status=c.status)

    vend_rows = session.execute(
        select(Vendor).where(Vendor.company_id == company_id)
    ).scalars().all()
    vend_by_id = {v.id: v for v in vend_rows}
    critical_vendor_id = None
    for v in vend_rows:
        add_node(v.id, "Vendor", v.name, criticality=v.criticality, category=v.category)
        if v.name == CRITICAL_VENDOR or v.criticality == "critical":
            critical_vendor_id = v.id

    prod_rows = session.execute(
        select(Product).where(Product.company_id == company_id)
    ).scalars().all()
    electronics_ids = []
    for p in prod_rows:
        add_node(p.id, "Product", p.name, line=p.line, sku=p.sku)
        if p.line == ELECTRONICS_LINE and critical_vendor_id:
            electronics_ids.append(p.id)
            edges.append(GraphEdge(critical_vendor_id, p.id, "SUPPLIES"))

    proj_rows = session.execute(
        select(Project).where(Project.company_id == company_id)
    ).scalars().all()
    for p in proj_rows:
        add_node(p.id, "Project", p.name, status=p.status, health=p.health)
        if p.department_id and p.department_id in dept_by_id:
            edges.append(GraphEdge(p.department_id, p.id, "OWNS"))
        if p.customer_id and p.customer_id in cust_by_id:
            edges.append(GraphEdge(p.id, p.customer_id, "DELIVERS_FOR"))

    pa_rows = session.execute(
        select(ProjectAssignment).where(ProjectAssignment.company_id == company_id)
    ).scalars().all()
    for pa in pa_rows:
        edges.append(
            GraphEdge(
                pa.employee_id,
                pa.project_id,
                "WORKS_ON",
                {"allocation_pct": float(pa.allocation_pct)},
            )
        )

    con_rows = session.execute(
        select(Contract).where(Contract.company_id == company_id)
    ).scalars().all()
    for c in con_rows:
        add_node(c.id, "Contract", c.title, value_cents=c.value_cents, status=c.status)
        if c.customer_id:
            edges.append(GraphEdge(c.customer_id, c.id, "SIGNED", {"role": "customer"}))
        if c.vendor_id:
            edges.append(GraphEdge(c.vendor_id, c.id, "SIGNED", {"role": "vendor"}))

    # PURCHASED + amounts from invoice line items
    purchased = session.execute(
        select(
            Invoice.customer_id,
            InvoiceLineItem.product_id,
            func.sum(InvoiceLineItem.amount_cents),
        )
        .join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
        .where(
            Invoice.company_id == company_id,
            InvoiceLineItem.product_id.isnot(None),
        )
        .group_by(Invoice.customer_id, InvoiceLineItem.product_id)
    ).all()
    for cust_id, prod_id, amt in purchased:
        if cust_id in cust_by_id and prod_id:
            edges.append(
                GraphEdge(
                    cust_id,
                    prod_id,
                    "PURCHASED",
                    {"amount_cents": int(amt or 0)},
                )
            )

    since = date.today().replace(day=1)
    since = since.replace(year=since.year - 1)

    rev_rows = session.execute(
        select(
            RevenueRecord.customer_id,
            func.sum(RevenueRecord.amount_cents),
        )
        .where(
            RevenueRecord.company_id == company_id,
            RevenueRecord.customer_id.isnot(None),
            RevenueRecord.period_month >= since,
        )
        .group_by(RevenueRecord.customer_id)
    ).all()
    for cust_id, amt in rev_rows:
        if cust_id in cust_by_id:
            edges.append(
                GraphEdge(
                    cust_id,
                    company_id,
                    "GENERATES_REVENUE",
                    {"amount_cents": int(amt or 0)},
                )
            )

    exp_rows = session.execute(
        select(Vendor.id, func.sum(Expense.amount_cents))
        .join(Expense, Expense.vendor_id == Vendor.id)
        .where(Expense.company_id == company_id, Expense.vendor_id.isnot(None))
        .group_by(Vendor.id)
    ).all()
    for vend_id, amt in exp_rows:
        if vend_id in vend_by_id:
            edges.append(
                GraphEdge(
                    vend_id,
                    company_id,
                    "INCURS_COST",
                    {"amount_cents": int(amt or 0)},
                )
            )

    # Supply Chain department depends on critical vendor
    scm_id = next((d.id for d in dept_rows if d.code == SCM_CODE), None)
    if scm_id and critical_vendor_id:
        edges.append(
            GraphEdge(scm_id, critical_vendor_id, "DEPENDS_ON", {"criticality": "critical"})
        )

    return GraphSnapshot(tenant_id=company_id, nodes=nodes, edges=edges)
