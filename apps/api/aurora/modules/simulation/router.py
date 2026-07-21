"""Decision simulation API routes (Phase 6)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_permission
from ...services.audit import record_audit
from ...services.simulation import (
    create_scenario,
    explain_simulation,
    get_scenario,
    get_simulation,
    list_scenarios,
    run_scenario,
)

router = APIRouter(tags=["simulation"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Simulations require DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


class ShockModel(BaseModel):
    type: str
    customer_id: Optional[str] = None
    probability: Optional[float] = 1.0
    category: Optional[str] = None
    department_code: Optional[str] = None
    pct_change: Optional[float] = None


class AssumptionsModel(BaseModel):
    shocks: List[Dict[str, Any]] = Field(default_factory=list)
    distributions: Dict[str, Any] = Field(default_factory=dict)


class ScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    horizon_periods: int = Field(12, ge=1, le=36)
    trials: int = Field(10000, ge=100, le=100000)
    assumptions: AssumptionsModel = Field(default_factory=AssumptionsModel)


@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
def post_scenario(
    body: ScenarioCreate,
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Session = Depends(_require_db),
) -> dict:
    data = create_scenario(
        session,
        context.tenant_id,
        name=body.name,
        assumptions=body.assumptions.model_dump(),
        horizon_periods=body.horizon_periods,
        trials=body.trials,
        created_by=context.user_id,
        description=body.description,
    )
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="scenario.create",
        resource_type="scenario",
        resource_id=data["id"],
        after={"name": body.name, "trials": body.trials},
    )
    return {
        "data": {"id": data["id"], "status": data["status"]},
        "meta": {"request_id": get_request_id()},
    }


@router.get("/scenarios/{scenario_id}")
def get_scenario_by_id(
    scenario_id: str,
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    data = get_scenario(scenario_id, session=session, company_id=context.tenant_id)
    if data is None or data.get("company_id") != context.tenant_id:
        raise NotFound("Scenario not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/scenarios")
def list_scenario_items(
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = list_scenarios(context.tenant_id, session=session)
    return {"data": items, "meta": {"request_id": get_request_id()}}


@router.post("/scenarios/{scenario_id}/run", status_code=status.HTTP_202_ACCEPTED)
def post_run_scenario(
    scenario_id: str,
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Session = Depends(_require_db),
) -> dict:
    data = get_scenario(scenario_id, session=session, company_id=context.tenant_id)
    if data is None or data.get("company_id") != context.tenant_id:
        raise NotFound("Scenario not found")
    try:
        result = run_scenario(session, context.tenant_id, scenario_id)
    except KeyError as exc:
        raise NotFound("Scenario not found") from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="simulation.run",
        resource_type="simulation",
        resource_id=result["id"],
        after={"scenario_id": scenario_id, "trials": result.get("trials")},
    )
    return {
        "data": {
            "simulation_id": result["id"],
            "status": "completed",
            "ws_channel": result.get("ws_channel"),
        },
        "meta": {"request_id": get_request_id()},
    }


@router.get("/simulations/{simulation_id}")
def get_simulation_by_id(
    simulation_id: str,
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    data = get_simulation(simulation_id, session=session, company_id=context.tenant_id)
    if data is None or data.get("company_id") != context.tenant_id:
        raise NotFound("Simulation not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/explain/simulation/{simulation_id}")
def explain_simulation_endpoint(
    simulation_id: str,
    context: AuthContext = Depends(require_permission(Permission.RUN_SIMULATION)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    sim = get_simulation(simulation_id, session=session, company_id=context.tenant_id)
    if sim is None or sim.get("company_id") != context.tenant_id:
        raise NotFound("Simulation not found")
    data = explain_simulation(simulation_id, session=session, company_id=context.tenant_id)
    return {"data": data, "meta": {"request_id": get_request_id()}}
