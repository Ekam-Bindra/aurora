"""Unit tests for the Monte Carlo simulation engine."""

from __future__ import annotations

import numpy as np

from aurora_sim.engine import BaselineState, MonteCarloEngine


def _baseline(**overrides) -> BaselineState:
    base = BaselineState(
        revenue_cents=3_000_000_00,
        cogs_cents=1_000_000_00,
        opex_cents=2_500_000_00,
        payroll_cents=1_200_000_00,
        cash_cents=4_250_000_00,
        gross_margin=0.67,
        runway_months=8.5,
        risk_scores={
            "liquidity": 55.0,
            "customer_concentration": 62.0,
            "operational": 45.0,
        },
        customer_revenue_pct={"cust_top": 0.14},
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_zero_shock_reproduces_baseline_runway():
    """Zero-shock scenario with zero growth must match baseline runway (§5.6 sanity bounds)."""
    baseline = _baseline()
    engine = MonteCarloEngine()
    result = engine.run(
        baseline,
        scenario_id="sc_zero",
        assumptions={
            "shocks": [],
            "distributions": {"revenue_growth_pct": {"dist": "normal", "mean": 0.0, "std": 0.0}},
        },
        horizon_periods=12,
        trials=5000,
        seed=42,
    )
    runway = result.results[0]["summary"]
    assert abs(runway["p50"] - baseline.runway_months) < 1.5


def test_customer_churn_reduces_runway():
    baseline = _baseline()
    engine = MonteCarloEngine()
    no_churn = engine.run(
        baseline,
        scenario_id="sc_base",
        assumptions={"shocks": [], "distributions": {}},
        trials=3000,
        seed=1,
    )
    with_churn = engine.run(
        baseline,
        scenario_id="sc_churn",
        assumptions={
            "shocks": [{"type": "customer_churn", "customer_id": "cust_top", "probability": 1.0}],
            "distributions": {},
        },
        trials=3000,
        seed=1,
    )
    assert with_churn.results[0]["summary"]["p50"] < no_churn.results[0]["summary"]["p50"]


def test_expense_change_reduces_runway():
    baseline = _baseline()
    engine = MonteCarloEngine()
    base = engine.run(
        baseline,
        scenario_id="sc_base",
        assumptions={"shocks": [], "distributions": {}},
        trials=3000,
        seed=2,
    )
    raised = engine.run(
        baseline,
        scenario_id="sc_raise",
        assumptions={
            "shocks": [
                {"type": "expense_change", "category": "payroll", "pct_change": 0.06},
            ],
            "distributions": {},
        },
        trials=3000,
        seed=2,
    )
    assert raised.results[0]["summary"]["p50"] < base.results[0]["summary"]["p50"]


def test_recommendations_generated_for_stress():
    baseline = _baseline(runway_months=4.0)
    engine = MonteCarloEngine()
    result = engine.run(
        baseline,
        scenario_id="sc_stress",
        assumptions={
            "shocks": [
                {"type": "customer_churn", "customer_id": "cust_top", "probability": 1.0},
                {"type": "expense_change", "category": "payroll", "pct_change": 0.06},
            ],
            "distributions": {"revenue_growth_pct": {"mean": -0.01, "std": 0.02}},
        },
        trials=2000,
        seed=3,
    )
    assert len(result.recommendations) >= 1
    assert result.risk_deltas["liquidity"] >= 0
    assert result.driver_sensitivity


def test_distribution_summary_stats():
    baseline = _baseline()
    engine = MonteCarloEngine()
    result = engine.run(
        baseline,
        scenario_id="sc_dist",
        assumptions={
            "shocks": [],
            "distributions": {"revenue_growth_pct": {"mean": 0.02, "std": 0.05}},
        },
        trials=10000,
        seed=99,
    )
    gm = result.results[1]["summary"]
    assert gm["p5"] <= gm["p50"] <= gm["p95"]
    assert "prob_below_3" in result.results[0]["summary"]


def test_monte_carlo_stderr():
    rng = np.random.default_rng(0)
    values = rng.normal(5.0, 1.0, size=10000)
    stderr = MonteCarloEngine.monte_carlo_stderr(values)
    assert 0.005 < stderr < 0.02
