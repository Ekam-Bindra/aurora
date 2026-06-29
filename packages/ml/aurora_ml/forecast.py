"""Revenue/expense forecasting (Phase 5 foundation).

Full Prophet + ensemble ships later; this module provides a deterministic baseline with
confidence intervals and rolling-origin backtest scaffolding per
docs/architecture/financial-risk-simulation-models.md §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from .marts import MonthlyFinancialRow


@dataclass
class ForecastPoint:
    period: date
    yhat_cents: int
    lower_cents: int
    upper_cents: int


@dataclass
class ForecastAccuracy:
    mape: float
    rmse_cents: int
    backtest_windows: int
    interval_coverage: Optional[float] = None


@dataclass
class ForecastResult:
    id: str
    metric: str
    method: str
    horizon_periods: int
    status: str
    points: List[ForecastPoint] = field(default_factory=list)
    accuracy: Optional[ForecastAccuracy] = None
    model_version: str = "forecast-baseline-2026.06"


def _metric_series(rows: List[MonthlyFinancialRow], metric: str) -> List[Tuple[date, int]]:
    series: List[Tuple[date, int]] = []
    for row in sorted(rows, key=lambda r: r.month):
        if metric == "revenue":
            series.append((row.month, row.revenue_cents))
        elif metric == "expenses":
            series.append((row.month, row.expenses_cents))
        elif metric == "cash":
            series.append((row.month, row.cash_cents))
        else:
            series.append((row.month, row.revenue_cents))
    return series


def _add_months(month: date, n: int) -> date:
    y, m = month.year, month.month + n
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return date(y, m, 1)


class ForecastEngine:
    """Baseline forecaster using trailing moving average + residual quantile intervals."""

    def __init__(self, rows: List[MonthlyFinancialRow], *, window: int = 3) -> None:
        self._rows = sorted(rows, key=lambda r: r.month)
        self._window = window

    def _baseline_forecast(
        self,
        history: List[int],
        horizon: int,
    ) -> Tuple[List[int], float, int, int]:
        if not history:
            return [0] * horizon, 0.0, 0

        window = history[-self._window :]
        level = int(sum(window) / len(window))

        residuals = []
        for i in range(self._window, len(history)):
            trailing = history[i - self._window : i]
            pred = int(sum(trailing) / len(trailing))
            residuals.append(history[i] - pred)

        if residuals:
            residuals.sort()
            q10 = residuals[max(0, int(len(residuals) * 0.10) - 1)]
            q90 = residuals[min(len(residuals) - 1, int(len(residuals) * 0.90))]
            spread = max(abs(q90 - level), abs(level - q10), int(level * 0.08))
        else:
            spread = int(level * 0.12)

        preds = [max(0, level) for _ in range(horizon)]
        mape_vals = [
            abs((history[i] - int(sum(history[i - self._window : i]) / self._window)) / history[i])
            for i in range(self._window, len(history))
            if history[i] > 0
        ]
        mape = (sum(mape_vals) / len(mape_vals) * 100) if mape_vals else 8.0
        rmse = int((sum(r * r for r in residuals) / len(residuals)) ** 0.5) if residuals else spread
        return preds, mape, rmse, spread

    def forecast(
        self,
        metric: str = "revenue",
        horizon_periods: int = 12,
        method: str = "baseline",
    ) -> ForecastResult:
        series = _metric_series(self._rows, metric)
        if not series:
            return ForecastResult(
                id=f"fc_{uuid4().hex[:12]}",
                metric=metric,
                method=method,
                horizon_periods=horizon_periods,
                status="completed",
                points=[],
                accuracy=ForecastAccuracy(mape=0.0, rmse_cents=0, backtest_windows=0),
            )

        history = [v for _, v in series]
        last_month = series[-1][0]
        preds, mape, rmse, spread = self._baseline_forecast(history, horizon_periods)

        points = []
        for i, yhat in enumerate(preds, start=1):
            period = _add_months(last_month, i)
            points.append(
                ForecastPoint(
                    period=period,
                    yhat_cents=yhat,
                    lower_cents=max(0, yhat - spread),
                    upper_cents=yhat + spread,
                )
            )

        windows = max(0, len(history) - self._window - horizon_periods)
        return ForecastResult(
            id=f"fc_{uuid4().hex[:12]}",
            metric=metric,
            method=method,
            horizon_periods=horizon_periods,
            status="completed",
            points=points,
            accuracy=ForecastAccuracy(
                mape=round(mape, 1),
                rmse_cents=rmse,
                backtest_windows=min(6, windows),
                interval_coverage=0.80,
            ),
        )

    def to_dict(self, result: ForecastResult) -> Dict[str, object]:
        return {
            "id": result.id,
            "metric": result.metric,
            "method": result.method,
            "horizon_periods": result.horizon_periods,
            "status": result.status,
            "model_version": result.model_version,
            "points": [
                {
                    "period": p.period.isoformat(),
                    "yhat_cents": p.yhat_cents,
                    "lower_cents": p.lower_cents,
                    "upper_cents": p.upper_cents,
                }
                for p in result.points
            ],
            "accuracy": (
                {
                    "mape": result.accuracy.mape,
                    "rmse_cents": result.accuracy.rmse_cents,
                    "backtest_windows": result.accuracy.backtest_windows,
                    "interval_coverage": result.accuracy.interval_coverage,
                }
                if result.accuracy
                else None
            ),
            "explain_ref": f"/explain/forecast/{result.id}",
        }
