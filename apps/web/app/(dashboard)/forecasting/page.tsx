"use client";

import { useCallback, useEffect, useState } from "react";
import ForecastFanChart from "@/components/forecast/ForecastFanChart";
import {
  createForecast,
  formatCents,
  getForecast,
  getMetricSeries,
  listForecasts,
  type ForecastData,
  type ForecastMethod,
  type MetricSeriesPoint,
} from "@/lib/api";

const METRICS = [
  { value: "revenue", label: "Revenue" },
  { value: "expenses", label: "Expenses" },
  { value: "cash", label: "Cash" },
] as const;

const HORIZONS = [3, 6, 12, 24] as const;

const METHODS: Array<{ value: ForecastMethod; label: string }> = [
  { value: "baseline", label: "Baseline" },
  { value: "sarimax", label: "SARIMAX" },
  { value: "ensemble", label: "Ensemble" },
  { value: "auto", label: "Auto (best of backtest)" },
];

export default function ForecastingPage() {
  const [metric, setMetric] = useState<string>("revenue");
  const [horizon, setHorizon] = useState<number>(12);
  const [method, setMethod] = useState<ForecastMethod>("baseline");
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [actuals, setActuals] = useState<MetricSeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadForecast = useCallback(async (m: string, h: number, meth: ForecastMethod) => {
    setLoading(true);
    setError(null);
    try {
      const [series, existing] = await Promise.all([
        getMetricSeries(m),
        listForecasts(),
      ]);

      // "auto" always re-runs the backtest; concrete methods reuse a matching
      // stored forecast when one exists.
      const match =
        meth === "auto"
          ? undefined
          : existing.find(
              (f) => f.metric === m && f.horizon_periods === h && f.method === meth,
            );
      let fc: ForecastData;
      if (match) {
        fc = await getForecast(match.id);
      } else {
        const created = await createForecast({ metric: m, horizon_periods: h, method: meth });
        fc = await getForecast(created.id);
      }

      setActuals(series);
      setForecast(fc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load forecast");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.resolve().then(() => loadForecast(metric, horizon, method));
  }, [metric, horizon, method, loadForecast]);

  const backtest = forecast?.accuracy?.backtest ?? null;

  return (
    <div className="p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Forecast Explorer</h1>
          <p className="text-sm text-text-muted">
            Actuals plus model forecast with confidence intervals from the financial engine.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="mr-2 text-text-muted">Metric</span>
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
              className="rounded-md border border-border bg-elevated px-2 py-1 text-sm"
            >
              {METRICS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm">
            <span className="mr-2 text-text-muted">Method</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as ForecastMethod)}
              className="rounded-md border border-border bg-elevated px-2 py-1 text-sm"
            >
              {METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm">
            <span className="mr-2 text-text-muted">Horizon</span>
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="rounded-md border border-border bg-elevated px-2 py-1 text-sm"
            >
              {HORIZONS.map((h) => (
                <option key={h} value={h}>
                  {h} mo
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-border bg-surface p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold capitalize">{metric} forecast fan chart</h2>
          {forecast && (
            <>
              <span className="rounded bg-elevated px-2 py-0.5 text-xs capitalize text-text-muted">
                {forecast.method}
              </span>
              {forecast.accuracy && (
                <>
                  <span className="text-xs text-text-muted">
                    MAPE {forecast.accuracy.mape.toFixed(1)}%
                  </span>
                  {forecast.accuracy.interval_coverage != null && (
                    <span className="text-xs text-text-muted">
                      Coverage {(forecast.accuracy.interval_coverage * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className="text-xs text-text-muted">
                    RMSE {formatCents(forecast.accuracy.rmse_cents)}
                  </span>
                </>
              )}
            </>
          )}
        </div>

        {loading ? (
          <p className="text-sm text-text-muted">Generating forecast…</p>
        ) : forecast ? (
          <ForecastFanChart actuals={actuals} forecast={forecast.points} />
        ) : null}
      </section>

      {backtest && (
        <section className="mt-6 rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Why this method</h2>
          <p className="mt-1 text-xs text-text-muted">
            Rolling-origin backtest over the last {backtest.holdout_points} months picked{" "}
            <span className="font-medium capitalize text-text-primary">{backtest.selected}</span>
            {" — lowest error on held-out actuals."}
            {backtest.fallback && (
              <span className="ml-1">({backtest.fallback.replace(/_/g, " ")})</span>
            )}
          </p>
          <table className="mt-3 w-full max-w-md text-sm">
            <thead>
              <tr className="text-left text-xs text-text-muted">
                <th className="pb-2">Method</th>
                <th className="pb-2 text-right">Backtest MAPE</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(backtest.mape_by_method)
                .sort(([, a], [, b]) => a - b)
                .map(([name, mape]) => (
                  <tr key={name} className="border-t border-border/60">
                    <td className="py-1.5 capitalize">
                      {name}
                      {name === backtest.selected && (
                        <span className="ml-2 rounded bg-positive/15 px-1.5 py-0.5 text-xs text-positive">
                          selected
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{mape.toFixed(1)}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}

      {forecast && forecast.points.length > 0 && (
        <section className="mt-6 rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Forecast points</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-text-muted">
                <th className="pb-2">Period</th>
                <th className="pb-2 text-right">Forecast</th>
                <th className="pb-2 text-right">Lower (80%)</th>
                <th className="pb-2 text-right">Upper (80%)</th>
              </tr>
            </thead>
            <tbody>
              {forecast.points.map((p) => (
                <tr key={p.period} className="border-t border-border/60">
                  <td className="py-2 text-text-muted">{p.period}</td>
                  <td className="py-2 text-right tabular-nums">{formatCents(p.yhat_cents)}</td>
                  <td className="py-2 text-right tabular-nums text-text-muted">
                    {formatCents(p.lower_cents)}
                  </td>
                  <td className="py-2 text-right tabular-nums text-text-muted">
                    {formatCents(p.upper_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
