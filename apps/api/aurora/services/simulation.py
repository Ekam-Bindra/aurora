"""Scenario and simulation orchestration.

Storage is dual-mode: with a session, scenarios live in the ``scenario`` table
and each run is a group of per-metric ``simulation_result`` rows sharing a
``run_id`` (visible to every API instance — ECS runs more than one task).
Without a session the per-process dicts back the in-memory test mode.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aurora_db.models.commercial import Customer
from aurora_db.models.financial import RevenueRecord
from aurora_db.models.intelligence import Scenario, SimulationResult
from aurora_db.types import new_uuid
from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import get_mart_rows
from aurora_sim.engine import BaselineState, MonteCarloEngine
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .risk import compute_genome, get_genome

_scenarios: Dict[str, Dict[str, Any]] = {}
_simulations: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_run_id(session: Session, scenario_id: str) -> Optional[str]:
    row = session.execute(
        select(SimulationResult.run_id)
        .where(SimulationResult.scenario_id == scenario_id)
        .order_by(SimulationResult.created_at.desc())
        .limit(1)
    ).first()
    return str(row[0]) if row is not None and row[0] is not None else None


def _scenario_row_to_dict(session: Session, row: Scenario) -> Dict[str, Any]:
    payload = {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "name": row.name,
        "description": row.description,
        "assumptions": row.assumptions or {},
        "horizon_periods": row.horizon_periods,
        "trials": row.trials,
        "status": row.status,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    latest = _latest_run_id(session, str(row.id))
    if latest is not None:
        payload["latest_simulation_id"] = latest
    return payload


def _get_scenario_row(
    session: Session, scenario_id: str, company_id: Optional[str]
) -> Optional[Scenario]:
    stmt = select(Scenario).where(Scenario.id == scenario_id)
    if company_id is not None:
        stmt = stmt.where(Scenario.company_id == company_id)
    return session.execute(stmt).scalar_one_or_none()


def _run_rows_to_dict(rows: List[SimulationResult]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    first = rows[0]
    run_id = str(first.run_id)
    return {
        "id": run_id,
        "scenario_id": str(first.scenario_id),
        "company_id": str(first.company_id),
        "status": "completed",
        "trials": first.trials,
        "seed": first.seed,
        "model_version": first.model_version,
        "results": [
            {"metric": r.metric, "summary": r.summary, "distribution": r.distribution}
            for r in rows
        ],
        "risk_deltas": first.risk_deltas,
        "recommendations": list(first.recommendations or []),
        "driver_sensitivity": list(first.driver_sensitivity or []),
        "explain_ref": f"/explain/simulation/{run_id}",
        "ws_channel": f"simulation:{run_id}",
        "completed_at": first.created_at.isoformat() if first.created_at else None,
    }


def _get_run_rows(
    session: Session, simulation_id: str, company_id: Optional[str]
) -> List[SimulationResult]:
    stmt = (
        select(SimulationResult)
        .where(SimulationResult.run_id == simulation_id)
        .order_by(SimulationResult.metric)
    )
    if company_id is not None:
        stmt = stmt.where(SimulationResult.company_id == company_id)
    return list(session.execute(stmt).scalars().all())


def _build_baseline(session: Session, company_id: str) -> BaselineState:
    rows = get_mart_rows(session, company_id)
    fin = FinancialEngine(rows)
    latest = fin.latest
    if latest is None:
        raise ValueError("No financial data for tenant")

    genome = get_genome(company_id)
    if genome is None:
        genome = compute_genome(session, company_id)

    risk_scores = {
        d["dimension"]: float(d["score"])
        for d in genome.get("dimensions", [])
    }

    rev_total = float(latest.revenue_cents) or 1.0
    cust_rows = session.execute(
        select(Customer.id, func.sum(RevenueRecord.amount_cents))
        .join(RevenueRecord, RevenueRecord.customer_id == Customer.id)
        .where(
            RevenueRecord.company_id == company_id,
            RevenueRecord.period_month == latest.month,
        )
        .group_by(Customer.id)
    ).all()
    if not cust_rows:
        cust_rows = session.execute(
            select(Customer.id, func.sum(RevenueRecord.amount_cents))
            .join(RevenueRecord, RevenueRecord.customer_id == Customer.id)
            .where(RevenueRecord.company_id == company_id)
            .group_by(Customer.id)
            .order_by(func.sum(RevenueRecord.amount_cents).desc())
            .limit(10)
        ).all()

    cust_pct: Dict[str, float] = {}
    total = sum(float(v or 0) for _, v in cust_rows) or rev_total
    for cid, amt in cust_rows:
        cust_pct[str(cid)] = float(amt or 0) / total

    opex = float(latest.expenses_cents - latest.cogs_cents)
    gm = fin.gross_margin(latest) or 0.0

    return BaselineState(
        revenue_cents=float(latest.revenue_cents),
        cogs_cents=float(latest.cogs_cents),
        opex_cents=opex,
        payroll_cents=float(latest.payroll_cents),
        cash_cents=float(latest.cash_cents),
        gross_margin=gm,
        runway_months=fin.cash_runway_months(),
        risk_scores=risk_scores,
        customer_revenue_pct=cust_pct,
    )


def create_scenario(
    session: Session,
    company_id: str,
    *,
    name: str,
    assumptions: Dict[str, Any],
    horizon_periods: int = 12,
    trials: int = 10000,
    created_by: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    if session is not None:
        row = Scenario(
            id=new_uuid(),
            company_id=company_id,
            name=name,
            description=description,
            assumptions=assumptions,
            horizon_periods=horizon_periods,
            trials=trials,
            status="draft",
            created_by=created_by,
        )
        session.add(row)
        session.flush()
        return _scenario_row_to_dict(session, row)

    sc_id = f"sc_{uuid.uuid4().hex[:12]}"
    payload = {
        "id": sc_id,
        "company_id": company_id,
        "name": name,
        "description": description,
        "assumptions": assumptions,
        "horizon_periods": horizon_periods,
        "trials": trials,
        "status": "draft",
        "created_by": created_by,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    _scenarios[sc_id] = payload
    return payload


def get_scenario(
    scenario_id: str,
    *,
    session: Optional[Session] = None,
    company_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if session is not None:
        row = _get_scenario_row(session, scenario_id, company_id)
        return _scenario_row_to_dict(session, row) if row is not None else None
    return _scenarios.get(scenario_id)


def list_scenarios(company_id: str, *, session: Optional[Session] = None) -> List[Dict[str, Any]]:
    if session is not None:
        rows = session.execute(
            select(Scenario)
            .where(Scenario.company_id == company_id)
            .order_by(Scenario.created_at.desc())
        ).scalars().all()
        return [_scenario_row_to_dict(session, r) for r in rows]
    return [s for s in _scenarios.values() if s.get("company_id") == company_id]


def run_scenario(
    session: Session,
    company_id: str,
    scenario_id: str,
    *,
    seed: int = 42,
) -> Dict[str, Any]:
    scenario_row: Optional[Scenario] = None
    if session is not None:
        scenario_row = _get_scenario_row(session, scenario_id, company_id)
        if scenario_row is None:
            raise KeyError("Scenario not found")
        assumptions = scenario_row.assumptions or {}
        horizon_periods = int(scenario_row.horizon_periods or 12)
        trials = int(scenario_row.trials or 10000)
        scenario_row.status = "running"
    else:
        scenario = _scenarios.get(scenario_id)
        if scenario is None or scenario.get("company_id") != company_id:
            raise KeyError("Scenario not found")
        assumptions = scenario.get("assumptions") or {}
        horizon_periods = int(scenario.get("horizon_periods", 12))
        trials = int(scenario.get("trials", 10000))
        scenario["status"] = "running"
        scenario["updated_at"] = _utcnow()

    baseline = _build_baseline(session, company_id)
    engine = MonteCarloEngine()
    result = engine.run(
        baseline,
        scenario_id=scenario_id,
        assumptions=assumptions,
        horizon_periods=horizon_periods,
        trials=trials,
        seed=seed,
    )

    if session is not None and scenario_row is not None:
        run_id = new_uuid()
        for block in result.results or []:
            session.add(
                SimulationResult(
                    id=new_uuid(),
                    company_id=company_id,
                    scenario_id=scenario_id,
                    run_id=run_id,
                    metric=block.get("metric", "unknown"),
                    summary=block.get("summary") or {},
                    distribution=block.get("distribution"),
                    risk_deltas=result.risk_deltas,
                    recommendations=result.recommendations or [],
                    driver_sensitivity=result.driver_sensitivity or [],
                    seed=result.seed,
                    trials=result.trials,
                    model_version=result.model_version,
                )
            )
        scenario_row.status = "completed"
        session.flush()
        rows = _get_run_rows(session, run_id, company_id)
        payload = _run_rows_to_dict(rows)
        if payload is not None:
            return payload
        # A run with no metric blocks has nothing to persist; fall through to the
        # transient payload so the caller still gets the engine output.

    payload = {
        "id": result.id,
        "scenario_id": scenario_id,
        "company_id": company_id,
        "status": result.status,
        "trials": result.trials,
        "seed": result.seed,
        "model_version": result.model_version,
        "results": result.results,
        "risk_deltas": result.risk_deltas,
        "recommendations": result.recommendations,
        "driver_sensitivity": result.driver_sensitivity,
        "explain_ref": f"/explain/simulation/{result.id}",
        "ws_channel": f"simulation:{result.id}",
        "completed_at": _utcnow(),
    }
    if session is None:
        _simulations[result.id] = payload
        scenario["status"] = "completed"
        scenario["latest_simulation_id"] = result.id
        scenario["updated_at"] = _utcnow()
    return payload


def get_simulation(
    simulation_id: str,
    *,
    session: Optional[Session] = None,
    company_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if session is not None:
        return _run_rows_to_dict(_get_run_rows(session, simulation_id, company_id))
    return _simulations.get(simulation_id)


def explain_simulation(
    simulation_id: str,
    *,
    session: Optional[Session] = None,
    company_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    sim = get_simulation(simulation_id, session=session, company_id=company_id)
    if sim is None:
        return None
    return {
        "simulation_id": simulation_id,
        "model_version": sim.get("model_version"),
        "driver_attribution": sim.get("driver_sensitivity") or [],
        "risk_deltas": sim.get("risk_deltas") or {},
        "evidence": [
            {"type": "scenario", "ref": f"/scenarios/{sim.get('scenario_id')}"},
            {"type": "metrics", "ref": "/metrics/overview"},
        ],
    }


def run_inline_simulation(
    session: Session,
    company_id: str,
    *,
    name: str,
    assumptions: Dict[str, Any],
    horizon_periods: int = 12,
    trials: int = 5000,
) -> Dict[str, Any]:
    """Create + run a scenario in one step (agent tool path)."""
    sc = create_scenario(
        session,
        company_id,
        name=name,
        assumptions=assumptions,
        horizon_periods=horizon_periods,
        trials=trials,
    )
    return run_scenario(session, company_id, sc["id"])
