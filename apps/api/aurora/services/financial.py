"""Financial metrics service — orchestrates aurora_ml over the tenant DB session."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from aurora_db.models import Customer, Expense, RevenueRecord, Vendor
from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import get_mart_rows
from aurora_ml.registry import METRIC_REGISTRY, get_metric
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _engine(session: Session, company_id: str) -> FinancialEngine:
    rows = get_mart_rows(session, company_id)
    return FinancialEngine(rows)


def metrics_overview(
    session: Session, company_id: str, as_of: Optional[date] = None
) -> Dict[str, Any]:
    engine = _engine(session, company_id)
    latest = engine.latest
    if latest is None:
        return {"as_of": None, "kpis": {}}

    as_of_month = as_of.replace(day=1) if as_of else latest.month
    row = engine.row_for_month(as_of_month) or latest
    gm = engine.gross_margin(row)
    om = engine.operating_margin(row)
    burn = engine.net_burn_cents()
    runway = engine.cash_runway_months()

    kpis: Dict[str, Any] = {
        "revenue_mtd": {
            "value_cents": row.revenue_cents,
            "currency": "USD",
            "delta_pct_yoy": engine.yoy_delta_pct("revenue", row.month),
        },
        "gross_margin": {
            "value": gm,
            "delta_pct_yoy": engine.yoy_delta_pct("gross_margin", row.month),
        },
        "operating_margin": {
            "value": om,
            "delta_pct_yoy": engine.yoy_delta_pct("operating_margin", row.month),
        },
        "net_burn": {"value_cents": burn, "currency": "USD"},
        "cash_runway_months": {
            "value": runway if runway is not None else 999.0,
            "trend": "down" if runway is not None and runway < 8 else "stable",
        },
    }
    return {
        "as_of": row.month.isoformat(),
        "kpis": kpis,
        "explain_ref": f"/api/v1/explain/metric/overview?as_of={row.month.isoformat()}",
    }


def metric_series(
    session: Session,
    company_id: str,
    metric: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> Dict[str, Any]:
    engine = _engine(session, company_id)
    points = []
    for month, value in engine.series(metric):
        if from_date and month < from_date.replace(day=1):
            continue
        if to_date and month > to_date.replace(day=1):
            continue
        if metric in ("gross_margin", "operating_margin"):
            points.append({"period": month.isoformat(), "value": value})
        else:
            points.append({"period": month.isoformat(), "value_cents": int(value)})
    return {"metric": metric, "granularity": "month", "currency": "USD", "points": points}


def concentration(session: Session, company_id: str) -> Dict[str, Any]:
    # Customer revenue concentration (last 12 months of data).
    engine = _engine(session, company_id)
    latest = engine.latest
    if not latest:
        return {"customers": [], "vendors": []}

    recent_start = latest.month.replace(year=latest.month.year - 1)

    customer_rows = session.execute(
        select(Customer.name, func.sum(RevenueRecord.amount_cents))
        .join(Customer, Customer.id == RevenueRecord.customer_id)
        .where(
            RevenueRecord.company_id == company_id,
            RevenueRecord.period_month >= recent_start,
        )
        .group_by(Customer.name)
        .order_by(func.sum(RevenueRecord.amount_cents).desc())
    ).all()

    vendor_rows = session.execute(
        select(Vendor.name, func.sum(Expense.amount_cents))
        .join(Vendor, Vendor.id == Expense.vendor_id)
        .where(Expense.company_id == company_id, Expense.vendor_id.isnot(None))
        .group_by(Vendor.name)
        .order_by(func.sum(Expense.amount_cents).desc())
    ).all()

    cust_amounts = [float(a) for _, a in customer_rows]
    vend_amounts = [float(a) for _, a in vendor_rows]
    cust_top, cust_hhi = FinancialEngine.concentration(cust_amounts)
    vend_top, vend_hhi = FinancialEngine.concentration(vend_amounts)

    def _top_list(rows, total) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "amount_cents": int(amt),
                "share": (float(amt) / total if total else 0.0),
            }
            for name, amt in rows[:10]
        ]

    cust_total = sum(cust_amounts) or 1.0
    vend_total = sum(vend_amounts) or 1.0

    return {
        "customers": {
            "top_5_share": cust_top,
            "hhi_normalized": cust_hhi,
            "top": _top_list(customer_rows, cust_total),
        },
        "vendors": {
            "top_5_share": vend_top,
            "hhi_normalized": vend_hhi,
            "top": _top_list(vendor_rows, vend_total),
        },
    }


def pnl_summary(
    session: Session, company_id: str, from_date: date, to_date: date
) -> Dict[str, Any]:
    engine = _engine(session, company_id)
    revenue = expenses = cogs = 0
    for row in engine.rows:
        if row.month < from_date.replace(day=1) or row.month > to_date.replace(day=1):
            continue
        revenue += row.revenue_cents
        expenses += row.expenses_cents
        cogs += row.cogs_cents
    gross = revenue - cogs
    net = revenue - expenses
    return {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "revenue_cents": revenue,
        "cogs_cents": cogs,
        "gross_profit_cents": gross,
        "expenses_cents": expenses,
        "net_profit_cents": net,
        "currency": "USD",
    }


def cash_summary(session: Session, company_id: str) -> Dict[str, Any]:
    engine = _engine(session, company_id)
    latest = engine.latest
    if not latest:
        return {}
    burn = engine.net_burn_cents()
    runway = engine.cash_runway_months()
    return {
        "cash_cents": latest.cash_cents,
        "net_burn_cents": burn,
        "runway_months": runway if runway is not None else None,
        "currency": "USD",
        "as_of": latest.month.isoformat(),
    }


def explain_metric(
    session: Session,
    company_id: str,
    metric_id: str,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    if metric_id == "overview":
        overview = metrics_overview(session, company_id, as_of)
        return {
            "metric": "overview",
            "formula": "Composite KPI snapshot (revenue_mtd, margins, burn, runway)",
            "formula_version": "2026.06",
            "inputs": overview.get("kpis", {}),
            "definitions": {k: v.formula for k, v in METRIC_REGISTRY.items()},
        }

    definition = get_metric(metric_id)
    engine = _engine(session, company_id)
    latest = engine.latest
    if definition is None or latest is None:
        return {"metric": metric_id, "error": "unknown metric or no data"}

    row = engine.row_for_month(as_of.replace(day=1)) if as_of else latest
    if row is None:
        row = latest

    inputs: Dict[str, Any] = {
        "revenue_cents": row.revenue_cents,
        "cogs_cents": row.cogs_cents,
        "expenses_cents": row.expenses_cents,
        "cash_cents": row.cash_cents,
        "month": row.month.isoformat(),
    }
    value: Any = None
    if metric_id == "gross_margin":
        value = engine.gross_margin(row)
    elif metric_id == "operating_margin":
        value = engine.operating_margin(row)
    elif metric_id == "net_burn":
        value = engine.net_burn_cents()
    elif metric_id == "cash_runway_months":
        value = engine.cash_runway_months()
    elif metric_id == "revenue" or metric_id == "revenue_mtd":
        value = row.revenue_cents

    return {
        "metric": metric_id,
        "name": definition.name,
        "formula": definition.formula,
        "formula_version": definition.formula_version,
        "unit": definition.unit,
        "inputs": inputs,
        "value": value,
    }
