"""Forecasting API routes (Phase 5 foundation)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_permission
from ...services.forecast import create_forecast, get_forecast, list_forecasts

router = APIRouter(tags=["forecasts"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Forecasts require DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


class ForecastCreate(BaseModel):
    metric: str = "revenue"
    granularity: str = "month"
    horizon_periods: int = Field(12, ge=1, le=24)
    method: str = "baseline"
    assumptions: Optional[dict] = None


@router.post("/forecasts", status_code=status.HTTP_202_ACCEPTED)
def post_forecast(
    body: ForecastCreate,
    context: AuthContext = Depends(require_permission(Permission.RUN_FORECAST)),
    session: Session = Depends(_require_db),
) -> dict:
    data = create_forecast(
        session,
        context.tenant_id,
        metric=body.metric,
        horizon_periods=body.horizon_periods,
        method=body.method,
    )
    return {
        "data": {"id": data["id"], "status": data["status"]},
        "meta": {"request_id": get_request_id()},
    }


@router.get("/forecasts/{forecast_id}")
def get_forecast_by_id(
    forecast_id: str,
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
) -> dict:
    data = get_forecast(forecast_id)
    if data is None or data.get("company_id") != context.tenant_id:
        raise NotFound("Forecast not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/forecasts")
def list_forecast_jobs(
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
) -> dict:
    items = list_forecasts(context.tenant_id)
    return {"data": {"forecasts": items}, "meta": {"request_id": get_request_id()}}
