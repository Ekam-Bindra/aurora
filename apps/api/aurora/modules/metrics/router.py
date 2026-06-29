"""Metrics API routes."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_permission
from ...services.financial import (
    cash_summary,
    concentration,
    metric_series,
    metrics_overview,
    pnl_summary,
)

router = APIRouter(tags=["metrics", "financials"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Financial metrics require DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/metrics/overview")
def overview(
    as_of: Optional[str] = Query(None),
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    data = metrics_overview(session, context.tenant_id, _parse_date(as_of))
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/metrics/{metric}/series")
def series(
    metric: str,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    data = metric_series(
        session,
        context.tenant_id,
        metric,
        _parse_date(from_date),
        _parse_date(to_date),
    )
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/metrics/concentration")
def concentration_metrics(
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    data = concentration(session, context.tenant_id)
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/financials/pnl")
def pnl(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    data = pnl_summary(
        session,
        context.tenant_id,
        date.fromisoformat(from_date),
        date.fromisoformat(to_date),
    )
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/financials/cash")
def cash(
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    data = cash_summary(session, context.tenant_id)
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/explain/metric/{metric_id}")
def explain_metric_endpoint(
    metric_id: str,
    as_of: Optional[str] = Query(None),
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Session = Depends(_require_db),
) -> dict:
    from ...services.financial import explain_metric

    data = explain_metric(session, context.tenant_id, metric_id, _parse_date(as_of))
    return {"data": data, "meta": {"request_id": get_request_id()}}
