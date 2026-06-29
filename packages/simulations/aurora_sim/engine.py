"""Vectorized Monte Carlo decision simulation (Models doc §5)."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

MODEL_VERSION = "sim-v1.0"


@dataclass
class BaselineState:
    """Financial baseline extracted from marts + risk genome."""

    revenue_cents: float
    cogs_cents: float
    opex_cents: float
    payroll_cents: float
    cash_cents: float
    gross_margin: float
    runway_months: Optional[float]
    risk_scores: Dict[str, float] = field(default_factory=dict)
    customer_revenue_pct: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationResult:
    id: str
    scenario_id: str
    status: str
    trials: int
    seed: int
    model_version: str
    results: List[Dict[str, Any]]
    risk_deltas: Dict[str, float]
    recommendations: List[Dict[str, Any]]
    driver_sensitivity: List[Dict[str, Any]]
    assumptions: Dict[str, Any] = field(default_factory=dict)


def _summary_stats(
    values: np.ndarray, *, prob_threshold: Optional[float] = None
) -> Dict[str, float]:
    out: Dict[str, float] = {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "p5": float(np.percentile(values, 5)),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
    }
    if prob_threshold is not None:
        out[f"prob_below_{prob_threshold:g}"] = float(np.mean(values < prob_threshold))
    return out


def _liquidity_score_from_runway(runway: float) -> float:
    """Map runway months to a 0–100 liquidity risk score (higher = worse)."""
    if runway >= 18:
        return 20.0
    if runway >= 12:
        return 35.0
    if runway >= 6:
        return 55.0
    if runway >= 3:
        return 75.0
    return 90.0


def _apply_shocks(
    baseline: BaselineState,
    shocks: List[Dict[str, Any]],
) -> tuple[float, float, float, float, Dict[str, float]]:
    """Return adjusted monthly revenue, cogs, opex, payroll and updated customer shares."""
    rev = float(baseline.revenue_cents)
    cogs = float(baseline.cogs_cents)
    opex = float(baseline.opex_cents)
    payroll = float(baseline.payroll_cents)
    cust_pct = dict(baseline.customer_revenue_pct)

    for shock in shocks:
        stype = shock.get("type", "")
        if stype == "customer_churn":
            cid = shock.get("customer_id", "")
            prob = float(shock.get("probability", 1.0))
            share = cust_pct.get(cid, 0.0)
            rev *= max(0.0, 1.0 - share * prob)
            cust_pct.pop(cid, None)
        elif stype == "expense_change":
            pct = float(shock.get("pct_change", 0.0))
            category = shock.get("category", "payroll")
            if category == "payroll":
                delta = payroll * pct
                payroll += delta
                opex += delta
            elif category == "cogs":
                cogs *= 1.0 + pct
            else:
                opex *= 1.0 + pct
        elif stype == "revenue_change":
            rev *= 1.0 + float(shock.get("pct_change", 0.0))

    return rev, cogs, opex, payroll, cust_pct


class MonteCarloEngine:
    """Vectorized Monte Carlo engine — trials are a NumPy axis."""

    def _simulate(
        self,
        baseline: BaselineState,
        *,
        shocks: List[Dict[str, Any]],
        distributions: Dict[str, Any],
        horizon_periods: int,
        trials: int,
        seed: int,
    ) -> tuple[List[Dict[str, Any]], float, Dict[str, float], np.ndarray]:
        base_rev, base_cogs, base_opex, _base_payroll, cust_pct = _apply_shocks(
            baseline, shocks
        )
        monthly_exp = base_cogs + base_opex

        rev_dist = distributions.get("revenue_growth_pct") or {}
        rev_mean = float(rev_dist.get("mean", 0.015))
        rev_std = float(rev_dist.get("std", 0.02))

        rng = np.random.default_rng(seed)
        growth = rng.normal(rev_mean, rev_std, size=(trials, horizon_periods))

        cum_growth = np.cumprod(1.0 + growth, axis=1)
        monthly_rev = base_rev * cum_growth
        monthly_exp_arr = np.broadcast_to(monthly_exp, (trials, horizon_periods)).copy()

        net_flow = monthly_rev - monthly_exp_arr
        cash_paths = np.zeros((trials, horizon_periods + 1), dtype=np.float64)
        cash_paths[:, 0] = baseline.cash_cents
        for h in range(horizon_periods):
            cash_paths[:, h + 1] = cash_paths[:, h] + net_flow[:, h]

        trailing_burn = np.mean(monthly_exp_arr - monthly_rev, axis=1)
        initial_runway = np.where(
            trailing_burn > 0,
            baseline.cash_cents / trailing_burn,
            999.0,
        )
        runway = initial_runway

        gross_margin = np.where(
            monthly_rev > 0,
            (monthly_rev - base_cogs) / monthly_rev,
            0.0,
        )
        final_gm = gross_margin[:, -1]
        final_cash = cash_paths[:, -1]

        results = [
            {
                "metric": "cash_runway_months",
                "summary": _summary_stats(runway, prob_threshold=3.0),
            },
            {
                "metric": "gross_margin",
                "summary": _summary_stats(final_gm),
            },
            {
                "metric": "cash_balance_cents",
                "summary": _summary_stats(final_cash),
            },
        ]
        median_runway = float(np.median(runway))
        return results, median_runway, cust_pct, runway

    def run(
        self,
        baseline: BaselineState,
        *,
        scenario_id: str,
        assumptions: Dict[str, Any],
        horizon_periods: int = 12,
        trials: int = 10000,
        seed: int = 42,
        simulation_id: Optional[str] = None,
        include_sensitivity: bool = True,
    ) -> SimulationResult:
        shocks = list(assumptions.get("shocks") or [])
        distributions = dict(assumptions.get("distributions") or {})

        results, median_runway, cust_pct, _runway = self._simulate(
            baseline,
            shocks=shocks,
            distributions=distributions,
            horizon_periods=horizon_periods,
            trials=trials,
            seed=seed,
        )

        risk_deltas = self._risk_deltas(baseline, median_runway, cust_pct, shocks)
        recommendations = self._recommendations(
            results, shocks, median_runway, baseline
        )
        sensitivity: List[Dict[str, Any]] = []
        if include_sensitivity:
            sensitivity = self._driver_sensitivity(
                baseline, shocks, distributions, horizon_periods, seed, results
            )

        return SimulationResult(
            id=simulation_id or f"sim_{uuid.uuid4().hex[:12]}",
            scenario_id=scenario_id,
            status="completed",
            trials=trials,
            seed=seed,
            model_version=MODEL_VERSION,
            results=results,
            risk_deltas=risk_deltas,
            recommendations=recommendations,
            driver_sensitivity=sensitivity,
            assumptions=assumptions,
        )

    def _risk_deltas(
        self,
        baseline: BaselineState,
        median_runway: float,
        cust_pct: Dict[str, float],
        shocks: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        base = baseline.risk_scores or {}
        sim_liquidity = _liquidity_score_from_runway(median_runway)
        deltas: Dict[str, float] = {
            "liquidity": round(sim_liquidity - base.get("liquidity", 50.0), 1),
        }

        top_share = max(cust_pct.values()) if cust_pct else 0.0
        conc_score = min(100.0, 30.0 + top_share * 200.0)
        base_conc = base.get("customer_concentration", conc_score)
        churned = any(s.get("type") == "customer_churn" for s in shocks)
        sim_conc = conc_score * (0.85 if churned else 1.0)
        deltas["customer_concentration"] = round(sim_conc - base_conc, 1)

        expense_shock = any(s.get("type") == "expense_change" for s in shocks)
        base_ops = base.get("operational", 45.0)
        sim_ops = base_ops + (8.0 if expense_shock else 0.0)
        deltas["operational"] = round(sim_ops - base_ops, 1)

        return deltas

    def _recommendations(
        self,
        results: List[Dict[str, Any]],
        shocks: List[Dict[str, Any]],
        median_runway: float,
        baseline: BaselineState,
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        runway_result = next(r for r in results if r["metric"] == "cash_runway_months")
        prob_low = runway_result["summary"].get("prob_below_3", 0.0)

        if prob_low > 0.35 or median_runway < 6:
            recs.append(
                {
                    "title": "Open a revolving credit line before Q4",
                    "priority": 1,
                    "expected_impact": {
                        "metric": "cash_runway_months",
                        "direction": "up",
                        "magnitude": "+2.5mo",
                    },
                }
            )

        if any(s.get("type") == "expense_change" for s in shocks):
            recs.append(
                {
                    "title": "Stage the engineering raise over two quarters",
                    "priority": 2,
                    "expected_impact": {
                        "metric": "cash_runway_months",
                        "direction": "up",
                        "magnitude": "+1.0mo",
                    },
                }
            )

        if any(s.get("type") == "customer_churn" for s in shocks):
            recs.append(
                {
                    "title": "Lock a 24-month retention deal with the top customer",
                    "priority": 2,
                }
            )

        if not recs and baseline.runway_months and baseline.runway_months < 12:
            recs.append(
                {
                    "title": "Accelerate accounts receivable collections",
                    "priority": 2,
                }
            )

        return recs[:5]

    def _driver_sensitivity(
        self,
        baseline: BaselineState,
        shocks: List[Dict[str, Any]],
        distributions: Dict[str, Any],
        horizon: int,
        seed: int,
        base_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """One-at-a-time sensitivity on revenue growth mean for explainability."""
        base_runway = base_results[0]["summary"]["p50"]

        drivers: List[Dict[str, Any]] = []
        rev_dist = distributions.get("revenue_growth_pct") or {}
        mean = float(rev_dist.get("mean", 0.015))
        for delta, label in [(-0.02, "revenue_growth_down"), (0.02, "revenue_growth_up")]:
            perturbed = dict(distributions)
            perturbed["revenue_growth_pct"] = {
                **rev_dist,
                "mean": mean + delta,
            }
            trial_results, _, _, _ = self._simulate(
                baseline,
                shocks=shocks,
                distributions=perturbed,
                horizon_periods=horizon,
                trials=2000,
                seed=seed + 1,
            )
            pert_runway = trial_results[0]["summary"]["p50"]
            impact = pert_runway - base_runway
            drivers.append(
                {
                    "driver": label,
                    "contribution_months": round(impact, 2),
                    "direction": "up" if impact > 0 else "down",
                }
            )

        for shock in shocks:
            stype = shock.get("type", "")
            if stype == "customer_churn":
                drivers.append(
                    {
                        "driver": "customer_churn",
                        "contribution_months": round(-base_runway * 0.15, 2),
                        "direction": "down",
                    }
                )
            elif stype == "expense_change":
                pct = float(shock.get("pct_change", 0.0))
                drivers.append(
                    {
                        "driver": "expense_change",
                        "contribution_months": round(-abs(pct) * base_runway * 2, 2),
                        "direction": "down",
                    }
                )

        drivers.sort(key=lambda d: abs(d["contribution_months"]), reverse=True)
        return drivers[:6]

    @staticmethod
    def monte_carlo_stderr(values: np.ndarray) -> float:
        return float(np.std(values) / math.sqrt(len(values)))
