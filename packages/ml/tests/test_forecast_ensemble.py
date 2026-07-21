"""SARIMAX, ensemble, and auto-selection forecast tests."""

import math
from datetime import date

import numpy as np

from aurora_ml.forecast import ForecastEngine
from aurora_ml.marts import MonthlyFinancialRow

_ACCURACY_KEYS = {"mape", "rmse_cents", "backtest_windows", "interval_coverage"}


def _seasonal_rows(n: int = 36) -> list:
    """Deterministic series: linear trend + strong 12-month seasonality + small seeded noise."""
    rng = np.random.default_rng(42)
    rows = []
    cash = 500_000_00
    for i in range(n):
        month = date(2023 + i // 12, i % 12 + 1, 1)
        seasonal = 1.0 + 0.30 * math.sin(2 * math.pi * (i % 12) / 12)
        trend = 4_000_000_00 + i * 60_000_00
        rev = max(1, int(trend * seasonal + rng.normal(0.0, 20_000_00)))
        exp = 3_500_000_00 + i * 40_000_00
        cash += rev - exp
        rows.append(
            MonthlyFinancialRow(
                company_id="co1",
                month=month,
                revenue_cents=rev,
                cogs_cents=int(rev * 0.55),
                expenses_cents=exp,
                payroll_cents=int(exp * 0.4),
                cash_cents=cash,
            )
        )
    return rows


def test_sarimax_contract_shape():
    engine = ForecastEngine(_seasonal_rows())
    result = engine.forecast(metric="revenue", horizon_periods=6, method="sarimax")
    assert result.status == "completed"
    assert result.method == "sarimax"
    assert "sarimax" in result.model_version
    assert len(result.points) == 6
    periods = [p.period for p in result.points]
    assert periods[0] == date(2026, 1, 1)
    assert all(earlier < later for earlier, later in zip(periods, periods[1:]))
    for p in result.points:
        assert p.yhat_cents > 0
        assert p.lower_cents <= p.yhat_cents <= p.upper_cents
    assert result.accuracy is not None
    assert result.accuracy.mape >= 0
    assert result.accuracy.backtest_windows > 0
    payload = engine.to_dict(result)
    assert set(payload["accuracy"].keys()) == _ACCURACY_KEYS


def test_ensemble_is_mean_of_baseline_and_sarimax():
    engine = ForecastEngine(_seasonal_rows())
    base = engine.forecast(metric="revenue", horizon_periods=4, method="baseline")
    sar = engine.forecast(metric="revenue", horizon_periods=4, method="sarimax")
    ens = engine.forecast(metric="revenue", horizon_periods=4, method="ensemble")
    assert ens.method == "ensemble"
    assert len(ens.points) == 4
    for b, s, e in zip(base.points, sar.points, ens.points):
        assert e.yhat_cents == (b.yhat_cents + s.yhat_cents) // 2
        # Conservative envelope: widest of the two members' intervals.
        assert e.lower_cents == min(b.lower_cents, s.lower_cents)
        assert e.upper_cents == max(b.upper_cents, s.upper_cents)
        assert e.lower_cents <= e.yhat_cents <= e.upper_cents


def test_auto_selects_lowest_mape_method():
    engine = ForecastEngine(_seasonal_rows())
    result = engine.forecast(metric="revenue", horizon_periods=6, method="auto")
    assert result.accuracy is not None
    block = result.accuracy.backtest
    assert block is not None
    assert set(block["mape_by_method"].keys()) == {"baseline", "sarimax", "ensemble"}
    assert block["holdout_points"] == 6
    selected = block["selected"]
    assert result.method == selected
    assert block["mape_by_method"][selected] == min(block["mape_by_method"].values())
    payload = engine.to_dict(result)
    assert set(payload["accuracy"].keys()) == _ACCURACY_KEYS | {"backtest"}
    assert payload["accuracy"]["backtest"]["selected"] == selected
    print("auto backtest:", block)


def test_auto_short_series_falls_back_to_baseline():
    engine = ForecastEngine(_seasonal_rows(12))
    result = engine.forecast(metric="revenue", horizon_periods=3, method="auto")
    assert result.method == "baseline"
    assert len(result.points) == 3
    block = result.accuracy.backtest
    assert block is not None
    assert block["selected"] == "baseline"
    assert block["fallback"] == "series_too_short_for_sarimax"
    assert 1 <= block["holdout_points"] <= 6


def test_baseline_accuracy_contract_unchanged():
    engine = ForecastEngine(_seasonal_rows())
    payload = engine.to_dict(engine.forecast(metric="revenue", horizon_periods=3))
    assert payload["method"] == "baseline"
    assert set(payload["accuracy"].keys()) == _ACCURACY_KEYS
