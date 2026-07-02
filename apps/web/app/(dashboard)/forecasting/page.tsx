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
  type MetricSeriesPoint,
} from "@/lib/api";

const METRICS = [
  { value: "revenue", label: "Revenue" },
  { value: "expenses", label: "Expenses" },
  { value: "cash", label: "Cash" },
] as const;

const HORIZONS = [3, 6, 12, 24] as const;

export default function ForecastingPage() {
  const [metric, setMetric] = useState<string>("revenue");
  const [horizon, setHorizon] = useState<number>(12);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [actuals, setActuals] = useState<MetricSeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadForecast = useCallback(async (m: string, h: number) => {
    setLoading(true);
    setError(null);
    try {
      const [series, existing] = await Promise.all([
        getMetricSeries(m),
        listForecasts(),
      ]);

      const match = existing.find((f) => f.metric === m && f.horizon_periods === h);
      let fc: ForecastData;
      if (match) {
        fc = await getForecast(match.id);
      } else {
        const created = await createForecast({ metric: m, horizon_periods: h, method: "baseline" });
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
    Promise.resolve().then(() => loadForecast(metric, horizon));
  }, [metric, horizon, loadForecast]);

  return (
    <div className="p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Forecast Explorer</h1>
          <p className="text-sm text-text-muted">
            Actuals plus baseline forecast with confidence intervals from the financial engine.
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
