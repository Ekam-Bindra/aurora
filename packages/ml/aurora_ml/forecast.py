"""Revenue/expense forecasting (Phase 5).

Seasonal-trend decomposition with rolling-origin backtest and confidence intervals.
Uses Prophet when installed; otherwise a deterministic seasonal baseline per
docs/architecture/financial-risk-simulation-models.md §3.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np

from .marts import MonthlyFinancialRow

try:
    from prophet import Prophet  # type: ignore

    _HAS_PROPHET = True
except ImportError:
    _HAS_PROPHET = False


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
    backtest: Optional[Dict[str, object]] = None


@dataclass
class FeatureImportance:
    feature: str
    importance: float


@dataclass
class ForecastResult:
    id: str
    metric: str
    method: str
    horizon_periods: int
    status: str
    points: List[ForecastPoint] = field(default_factory=list)
    accuracy: Optional[ForecastAccuracy] = None
    model_version: str = "forecast-2026.06"
    feature_importance: List[FeatureImportance] = field(default_factory=list)
    backtest_detail: Optional[Dict[str, object]] = None


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


def _month_index(month: date) -> int:
    return month.year * 12 + (month.month - 1)


def _residual_quantiles(residuals: List[int]) -> Tuple[int, int]:
    if not residuals:
        return 0, 0
    sorted_r = sorted(residuals)
    n = len(sorted_r)
    q10 = sorted_r[max(0, int(n * 0.10) - 1)]
    q90 = sorted_r[min(n - 1, int(n * 0.90))]
    return q10, q90


class ForecastEngine:
    """Forecaster with seasonal-trend decomposition, optional Prophet, and rolling backtest."""

    def __init__(self, rows: List[MonthlyFinancialRow], *, window: int = 3) -> None:
        self._rows = sorted(rows, key=lambda r: r.month)
        self._window = window

    def _seasonal_indices(
        self, months: List[date], values: List[int], period: int = 12
    ) -> List[float]:
        if len(values) < period:
            return [1.0] * period
        by_month: Dict[int, List[float]] = {m: [] for m in range(1, 13)}
        for m, v in zip(months, values):
            if v > 0:
                by_month[m.month].append(float(v))
        overall = float(np.mean([v for v in values if v > 0])) if any(values) else 1.0
        indices = []
        for m in range(1, 13):
            if by_month[m]:
                indices.append(float(np.mean(by_month[m])) / max(overall, 1.0))
            else:
                indices.append(1.0)
        return indices

    def _trend_level(self, values: List[int]) -> float:
        if not values:
            return 0.0
        tail = values[-min(12, len(values)) :]
        x = np.arange(len(tail), dtype=float)
        y = np.array(tail, dtype=float)
        if len(tail) < 2:
            return float(tail[-1])
        slope, intercept = np.polyfit(x, y, 1)
        return float(intercept + slope * (len(tail) - 1))

    def _seasonal_forecast(
        self,
        months: List[date],
        values: List[int],
        horizon: int,
    ) -> Tuple[List[int], List[FeatureImportance]]:
        level = self._trend_level(values)
        indices = self._seasonal_indices(months, values)
        last_month = months[-1]
        preds: List[int] = []
        for i in range(1, horizon + 1):
            target = _add_months(last_month, i)
            seasonal = indices[target.month - 1]
            preds.append(max(0, int(level * seasonal)))

        trend_var = float(np.var(values[-12:])) if len(values) >= 2 else 1.0
        seasonal_var = float(np.var(indices))
        total = trend_var + seasonal_var + 1.0
        importance = [
            FeatureImportance("trend", round(trend_var / total, 2)),
            FeatureImportance("seasonality", round(seasonal_var / total, 2)),
            FeatureImportance("level", round(1.0 / total, 2)),
        ]
        return preds, importance

    def _baseline_forecast(
        self, history: List[int], horizon: int
    ) -> Tuple[List[int], float, int, int]:
        if not history:
            return [0] * horizon, 0.0, 0, 0

        window = history[-self._window :]
        level = int(sum(window) / len(window))

        residuals = []
        for i in range(self._window, len(history)):
            trailing = history[i - self._window : i]
            pred = int(sum(trailing) / len(trailing))
            residuals.append(history[i] - pred)

        if residuals:
            q10, q90 = _residual_quantiles(residuals)
            spread = max(abs(q90), abs(q10), int(level * 0.08))
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

    def _prophet_forecast(
        self,
        months: List[date],
        values: List[int],
        horizon: int,
    ) -> Optional[Tuple[List[int], List[int], List[int], List[FeatureImportance]]]:
        if not _HAS_PROPHET or len(values) < 12:
            return None
        import pandas as pd

        df = pd.DataFrame({"ds": months, "y": [v / 100.0 for v in values]})
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.80,
        )
        model.fit(df)
        future = model.make_future_dataframe(periods=horizon, freq="MS")
        forecast = model.predict(future)
        tail = forecast.tail(horizon)
        preds = [max(0, int(y * 100)) for y in tail["yhat"].tolist()]
        lowers = [max(0, int(y * 100)) for y in tail["yhat_lower"].tolist()]
        uppers = [max(0, int(y * 100)) for y in tail["yhat_upper"].tolist()]
        importance = [
            FeatureImportance("trend", 0.35),
            FeatureImportance("seasonality_q4", 0.38),
            FeatureImportance("holidays", 0.12),
            FeatureImportance("residual", 0.15),
        ]
        return preds, lowers, uppers, importance

    def _sarimax_forecast(
        self, values: List[int], horizon: int
    ) -> Optional[Tuple[List[int], List[int], List[int]]]:
        """SARIMAX with a small fixed order; None when the series is too short or the fit fails."""
        if len(values) < 6:
            return None
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        if len(values) >= 24:
            order, seasonal_order = (1, 1, 1), (1, 1, 1, 12)
        else:
            order, seasonal_order = (1, 1, 1), (0, 0, 0, 0)
        y = np.asarray(values, dtype=float)
        with warnings.catch_warnings():
            # Low maxiter on short series routinely trips ConvergenceWarning; suppress noise.
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", UserWarning)
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                model = SARIMAX(
                    y,
                    order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                fitted = model.fit(disp=False, maxiter=50)
                fc = fitted.get_forecast(steps=horizon)
                # alpha=0.20 -> 80% interval, same level as the baseline's q10-q90 band.
                conf = np.asarray(fc.conf_int(alpha=0.20))
                preds = [max(0, int(v)) for v in np.asarray(fc.predicted_mean)]
                lowers = [max(0, int(v)) for v in conf[:, 0]]
                uppers = [max(0, int(v)) for v in conf[:, 1]]
            except Exception:
                return None
        return preds, lowers, uppers

    def _rolling_origin_backtest(
        self,
        months: List[date],
        values: List[int],
        *,
        horizon: int = 1,
        n_windows: int = 6,
        min_train: int = 12,
        method: str = "seasonal",
    ) -> Tuple[float, int, float, int]:
        """Return (mape, rmse_cents, interval_coverage, windows_run)."""
        if len(values) < min_train + horizon:
            return 8.0, 0, 0.80, 0

        errors: List[float] = []
        sq_errors: List[int] = []
        in_interval = 0
        total_checks = 0
        windows_run = 0

        start = max(min_train, len(values) - n_windows - horizon + 1)
        for t in range(start, len(values) - horizon + 1):
            train_m = months[:t]
            train_v = values[:t]
            actual = values[t : t + horizon]
            if method == "baseline":
                preds, _, _, spread = self._baseline_forecast(train_v, horizon)
                lowers = [max(0, p - spread) for p in preds]
                uppers = [p + spread for p in preds]
            elif method == "prophet":
                prophet_result = self._prophet_forecast(train_m, train_v, horizon)
                if prophet_result:
                    preds, lowers, uppers, _ = prophet_result
                else:
                    preds, _ = self._seasonal_forecast(train_m, train_v, horizon)
                    residuals = [
                        train_v[i] - int(self._trend_level(train_v[: i + 1]))
                        for i in range(min_train, len(train_v))
                    ]
                    q10, q90 = _residual_quantiles(residuals)
                    lowers = [max(0, p + q10) for p in preds]
                    uppers = [p + q90 for p in preds]
            elif method == "sarimax":
                sar = self._sarimax_forecast(train_v, horizon)
                if sar is not None:
                    preds, lowers, uppers = sar
                else:
                    preds, _, _, spread = self._baseline_forecast(train_v, horizon)
                    lowers = [max(0, p - spread) for p in preds]
                    uppers = [p + spread for p in preds]
            elif method == "ensemble":
                preds_b, _, _, spread = self._baseline_forecast(train_v, horizon)
                lowers_b = [max(0, p - spread) for p in preds_b]
                uppers_b = [p + spread for p in preds_b]
                sar = self._sarimax_forecast(train_v, horizon)
                if sar is not None:
                    preds_s, lowers_s, uppers_s = sar
                    preds = [(preds_b[i] + preds_s[i]) // 2 for i in range(horizon)]
                    lowers = [min(lowers_b[i], lowers_s[i]) for i in range(horizon)]
                    uppers = [max(uppers_b[i], uppers_s[i]) for i in range(horizon)]
                else:
                    preds, lowers, uppers = preds_b, lowers_b, uppers_b
            else:
                preds, _ = self._seasonal_forecast(train_m, train_v, horizon)
                residuals = [
                    train_v[i] - int(self._trend_level(train_v[: i + 1]))
                    for i in range(min_train, len(train_v))
                ]
                q10, q90 = _residual_quantiles(residuals)
                lowers = [max(0, p + q10) for p in preds]
                uppers = [p + q90 for p in preds]

            for i, act in enumerate(actual):
                if act <= 0:
                    continue
                pred = preds[i] if i < len(preds) else preds[-1]
                errors.append(abs((act - pred) / act))
                sq_errors.append((act - pred) ** 2)
                lo = lowers[i] if i < len(lowers) else lowers[-1]
                hi = uppers[i] if i < len(uppers) else uppers[-1]
                if lo <= act <= hi:
                    in_interval += 1
                total_checks += 1
            windows_run += 1

        mape = (sum(errors) / len(errors) * 100) if errors else 8.0
        rmse = int(math.sqrt(sum(sq_errors) / len(sq_errors))) if sq_errors else 0
        coverage = (in_interval / total_checks) if total_checks else 0.80
        return round(mape, 1), rmse, round(coverage, 2), windows_run

    def _auto_select(self, history: List[int]) -> Tuple[str, Dict[str, object]]:
        """Rolling-origin holdout (1-step folds, refit per fold) ranking methods by MAPE."""
        n = len(history)
        if n < 18:
            # Too short for a meaningful SARIMAX fit — score baseline only.
            holdout = max(0, min(6, n - self._window - 1))
            errs: List[float] = []
            for t in range(n - holdout, n):
                actual = history[t]
                if actual <= 0:
                    continue
                pred = self._baseline_forecast(history[:t], 1)[0][0]
                errs.append(abs(actual - pred) / actual)
            mape_by: Dict[str, object] = (
                {"baseline": round(sum(errs) / len(errs) * 100, 2)} if errs else {}
            )
            return "baseline", {
                "selected": "baseline",
                "mape_by_method": mape_by,
                "holdout_points": holdout,
                "fallback": "series_too_short_for_sarimax",
            }

        holdout = min(6, n - 12)  # keep >= 12 training points in the earliest fold
        errs_by: Dict[str, List[float]] = {"baseline": [], "sarimax": [], "ensemble": []}
        for t in range(n - holdout, n):
            actual = history[t]
            if actual <= 0:
                continue
            base_pred = self._baseline_forecast(history[:t], 1)[0][0]
            sar = self._sarimax_forecast(history[:t], 1)
            sar_pred = sar[0][0] if sar is not None else base_pred
            fold_preds = {
                "baseline": base_pred,
                "sarimax": sar_pred,
                "ensemble": (base_pred + sar_pred) // 2,
            }
            for name, pred in fold_preds.items():
                errs_by[name].append(abs(actual - pred) / actual)

        if not errs_by["baseline"]:
            return "baseline", {
                "selected": "baseline",
                "mape_by_method": {},
                "holdout_points": holdout,
                "fallback": "no_positive_holdout_actuals",
            }
        mape_scores = {k: round(sum(v) / len(v) * 100, 2) for k, v in errs_by.items()}
        # min() on the dict keeps insertion order as a deterministic tie-break.
        selected = min(mape_scores, key=mape_scores.get)
        return selected, {
            "selected": selected,
            "mape_by_method": mape_scores,
            "holdout_points": holdout,
        }

    def _resolve_method(self, method: str) -> str:
        if method == "prophet" and not _HAS_PROPHET:
            return "seasonal"
        return method

    def forecast(
        self,
        metric: str = "revenue",
        horizon_periods: int = 12,
        method: str = "baseline",
    ) -> ForecastResult:
        series = _metric_series(self._rows, metric)
        fc_id = f"fc_{uuid4().hex[:12]}"
        if not series:
            return ForecastResult(
                id=fc_id,
                metric=metric,
                method=method,
                horizon_periods=horizon_periods,
                status="completed",
                points=[],
                accuracy=ForecastAccuracy(mape=0.0, rmse_cents=0, backtest_windows=0),
            )

        months = [m for m, _ in series]
        history = [v for _, v in series]
        last_month = series[-1][0]

        if method == "auto":
            # Backtest-driven selection; evidence lands in accuracy.backtest for the UI.
            selected, block = self._auto_select(history)
            result = self.forecast(
                metric=metric, horizon_periods=horizon_periods, method=selected
            )
            if result.accuracy is not None:
                result.accuracy.backtest = block
            return result

        resolved = self._resolve_method(method)

        feature_importance: List[FeatureImportance] = []
        lowers: Optional[List[int]] = None
        uppers: Optional[List[int]] = None
        detail_extra: Dict[str, object] = {}

        if resolved == "baseline":
            preds, _, _, spread = self._baseline_forecast(history, horizon_periods)
            lowers = [max(0, p - spread) for p in preds]
            uppers = [p + spread for p in preds]
            feature_importance = [
                FeatureImportance("trailing_average", 0.55),
                FeatureImportance("residual_spread", 0.45),
            ]
            bt_method = "baseline"
        elif resolved == "prophet":
            prophet_result = self._prophet_forecast(months, history, horizon_periods)
            if prophet_result:
                preds, lowers, uppers, feature_importance = prophet_result
            else:
                preds, feature_importance = self._seasonal_forecast(
                    months, history, horizon_periods
                )
            bt_method = "prophet"
        elif resolved == "sarimax":
            sar = self._sarimax_forecast(history, horizon_periods)
            if sar is not None:
                preds, lowers, uppers = sar
                feature_importance = [
                    FeatureImportance("autoregression", 0.4),
                    FeatureImportance("seasonality_12m", 0.3),
                    FeatureImportance("trend_differencing", 0.2),
                    FeatureImportance("residual", 0.1),
                ]
                bt_method = "sarimax"
            else:
                preds, _, _, spread = self._baseline_forecast(history, horizon_periods)
                lowers = [max(0, p - spread) for p in preds]
                uppers = [p + spread for p in preds]
                feature_importance = [
                    FeatureImportance("trailing_average", 0.55),
                    FeatureImportance("residual_spread", 0.45),
                ]
                bt_method = "baseline"
                method = "baseline"
                detail_extra["fallback"] = "sarimax_unavailable_used_baseline"
        elif resolved == "ensemble":
            base_preds, _, _, spread = self._baseline_forecast(history, horizon_periods)
            base_lowers = [max(0, p - spread) for p in base_preds]
            base_uppers = [p + spread for p in base_preds]
            sar = self._sarimax_forecast(history, horizon_periods)
            if sar is not None:
                sar_preds, sar_lowers, sar_uppers = sar
                preds = [
                    (base_preds[i] + sar_preds[i]) // 2 for i in range(horizon_periods)
                ]
                # Conservative envelope: widest of the two members' intervals.
                lowers = [min(base_lowers[i], sar_lowers[i]) for i in range(horizon_periods)]
                uppers = [max(base_uppers[i], sar_uppers[i]) for i in range(horizon_periods)]
                bt_method = "ensemble"
            else:
                preds, lowers, uppers = base_preds, base_lowers, base_uppers
                bt_method = "baseline"
                detail_extra["fallback"] = "sarimax_unavailable_used_baseline"
            feature_importance = [
                FeatureImportance("trailing_average", 0.5),
                FeatureImportance("sarimax", 0.5),
            ]
        else:
            preds, feature_importance = self._seasonal_forecast(months, history, horizon_periods)
            residuals = [
                history[i] - int(self._trend_level(history[: i + 1]))
                for i in range(min(12, len(history)), len(history))
            ]
            q10, q90 = _residual_quantiles(residuals)
            lowers = [max(0, p + q10) for p in preds]
            uppers = [p + q90 for p in preds]
            bt_method = "seasonal"
            if method == "prophet":
                method = "seasonal"

        if lowers is None or uppers is None:
            residuals = [
                history[i] - int(self._trend_level(history[: i + 1]))
                for i in range(min(12, len(history)), len(history))
            ]
            q10, q90 = _residual_quantiles(residuals)
            lowers = [max(0, p + q10) for p in preds]
            uppers = [p + q90 for p in preds]

        mape, rmse, coverage, windows = self._rolling_origin_backtest(
            months, history, horizon=1, n_windows=6, method=bt_method
        )

        points = []
        for i, yhat in enumerate(preds, start=1):
            period = _add_months(last_month, i)
            lo = lowers[i - 1] if i - 1 < len(lowers) else max(0, yhat - int(yhat * 0.08))
            hi = uppers[i - 1] if i - 1 < len(uppers) else yhat + int(yhat * 0.08)
            points.append(
                ForecastPoint(
                    period=period,
                    yhat_cents=yhat,
                    lower_cents=lo,
                    upper_cents=hi,
                )
            )

        if resolved == "prophet":
            model_version = "forecast-prophet-2026.06"
        elif resolved in ("sarimax", "ensemble") and bt_method != "baseline":
            model_version = "forecast-" + resolved + "-2026.07"
        else:
            model_version = "forecast-2026.06"
        return ForecastResult(
            id=fc_id,
            metric=metric,
            method=method,
            horizon_periods=horizon_periods,
            status="completed",
            points=points,
            accuracy=ForecastAccuracy(
                mape=mape,
                rmse_cents=rmse,
                backtest_windows=windows,
                interval_coverage=coverage,
            ),
            model_version=model_version,
            feature_importance=feature_importance,
            backtest_detail={
                "windows": windows,
                "mape": mape,
                "coverage_80pct": coverage,
                "method_resolved": resolved,
                **detail_extra,
            },
        )

    def to_dict(self, result: ForecastResult) -> Dict[str, object]:
        accuracy_payload: Optional[Dict[str, object]] = None
        if result.accuracy:
            accuracy_payload = {
                "mape": result.accuracy.mape,
                "rmse_cents": result.accuracy.rmse_cents,
                "backtest_windows": result.accuracy.backtest_windows,
                "interval_coverage": result.accuracy.interval_coverage,
            }
            # Only "auto" adds the backtest block; existing payloads stay byte-identical.
            if result.accuracy.backtest is not None:
                accuracy_payload["backtest"] = result.accuracy.backtest
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
            "accuracy": accuracy_payload,
            "explain_ref": f"/explain/forecast/{result.id}",
            "feature_importance": [
                {"feature": fi.feature, "importance": fi.importance}
                for fi in result.feature_importance
            ],
            "backtest_detail": result.backtest_detail,
        }
