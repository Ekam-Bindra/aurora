"""Scenario and simulation orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aurora_db.models.commercial import Customer
from aurora_db.models.financial import RevenueRecord
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


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    return _scenarios.get(scenario_id)


def list_scenarios(company_id: str) -> List[Dict[str, Any]]:
    return [s for s in _scenarios.values() if s.get("company_id") == company_id]


def run_scenario(
    session: Session,
    company_id: str,
    scenario_id: str,
    *,
    seed: int = 42,
) -> Dict[str, Any]:
    scenario = _scenarios.get(scenario_id)
    if scenario is None or scenario.get("company_id") != company_id:
        raise KeyError("Scenario not found")

    scenario["status"] = "running"
    scenario["updated_at"] = _utcnow()

    baseline = _build_baseline(session, company_id)
    engine = MonteCarloEngine()
    result = engine.run(
        baseline,
        scenario_id=scenario_id,
        assumptions=scenario.get("assumptions") or {},
        horizon_periods=int(scenario.get("horizon_periods", 12)),
        trials=int(scenario.get("trials", 10000)),
        seed=seed,
    )

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
    _simulations[result.id] = payload
    scenario["status"] = "completed"
    scenario["latest_simulation_id"] = result.id
    scenario["updated_at"] = _utcnow()
    return payload


def get_simulation(simulation_id: str) -> Optional[Dict[str, Any]]:
    return _simulations.get(simulation_id)


def explain_simulation(simulation_id: str) -> Optional[Dict[str, Any]]:
    sim = _simulations.get(simulation_id)
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
