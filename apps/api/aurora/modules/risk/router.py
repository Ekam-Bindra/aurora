"""Risk Genome API routes (Phase 5 foundation)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_any_permission, require_permission
from ...services.risk import compute_genome, genome_history, get_dimension, get_genome

router = APIRouter(tags=["risk"])

_READ_RISK = require_any_permission(Permission.READ_FINANCIALS, Permission.READ_OPERATIONS)


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Risk genome requires DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


@router.get("/risk/genome")
def risk_genome(
    context: AuthContext = Depends(_READ_RISK),
    session: Session = Depends(_require_db),
) -> dict:
    cached = get_genome(context.tenant_id)
    data = cached if cached else compute_genome(session, context.tenant_id)
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/risk/genome/history")
def risk_genome_history(
    context: AuthContext = Depends(_READ_RISK),
    session: Session = Depends(_require_db),
) -> dict:
    if get_genome(context.tenant_id) is None:
        compute_genome(session, context.tenant_id)
    data = {"history": genome_history(context.tenant_id)}
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/risk/genome/{dimension}")
def risk_genome_dimension(
    dimension: str,
    context: AuthContext = Depends(_READ_RISK),
    session: Session = Depends(_require_db),
) -> dict:
    if get_genome(context.tenant_id) is None:
        compute_genome(session, context.tenant_id)
    data = get_dimension(context.tenant_id, dimension)
    if data is None:
        raise NotFound(f"Risk dimension '{dimension}' not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.post("/risk/recompute", status_code=status.HTTP_202_ACCEPTED)
def risk_recompute(
    context: AuthContext = Depends(require_permission(Permission.RUN_FORECAST)),
    session: Session = Depends(_require_db),
) -> dict:
    data = compute_genome(session, context.tenant_id)
    return {
        "data": {"status": "completed", "computed_at": data["computed_at"]},
        "meta": {"request_id": get_request_id()},
    }
