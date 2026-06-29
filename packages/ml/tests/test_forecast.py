"""Forecast service tests."""

from datetime import date

from aurora_ml.forecast import ForecastEngine
from aurora_ml.marts import MonthlyFinancialRow


def _sample_rows(n: int = 24) -> list:
    rows = []
    cash = 500_000_00
    for i in range(n):
        month = date(2024, (i % 12) + 1, 1)
        rev = 4_000_000_00 + i * 50_000_00
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


def test_forecast_returns_points_and_accuracy():
    engine = ForecastEngine(_sample_rows())
    result = engine.forecast(metric="revenue", horizon_periods=6)
    assert result.status == "completed"
    assert len(result.points) == 6
    assert result.points[0].yhat_cents > 0
    assert result.points[0].lower_cents <= result.points[0].yhat_cents
    assert result.accuracy is not None
    assert result.accuracy.mape >= 0


def test_forecast_to_dict():
    engine = ForecastEngine(_sample_rows())
    result = engine.forecast(horizon_periods=3)
    payload = engine.to_dict(result)
    assert payload["id"] == result.id
    assert len(payload["points"]) == 3
    assert "explain_ref" in payload
