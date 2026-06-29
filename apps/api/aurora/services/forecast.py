"""Forecast service — orchestrates aurora_ml over tenant financial marts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aurora_ml.forecast import ForecastEngine, ForecastResult
from aurora_ml.marts import get_mart_rows
from sqlalchemy.orm import Session

# In-memory forecast store (Phase 5 — Redis/job queue in later iterations).
_forecasts: Dict[str, Dict[str, Any]] = {}


def _engine(session: Session, company_id: str) -> ForecastEngine:
    rows = get_mart_rows(session, company_id)
    return ForecastEngine(rows)


def create_forecast(
    session: Session,
    company_id: str,
    *,
    metric: str = "revenue",
    horizon_periods: int = 12,
    method: str = "baseline",
) -> Dict[str, Any]:
    fc_engine = _engine(session, company_id)
    result: ForecastResult = fc_engine.forecast(
        metric=metric,
        horizon_periods=horizon_periods,
        method=method,
    )
    payload = fc_engine.to_dict(result)
    payload["company_id"] = company_id
    _forecasts[result.id] = payload
    return payload

def get_forecast(forecast_id: str) -> Optional[Dict[str, Any]]:
    return _forecasts.get(forecast_id)


def list_forecasts(company_id: str) -> List[Dict[str, Any]]:
    return [f for f in _forecasts.values() if f.get("company_id") == company_id]
