"use client";

import { useEffect, useState } from "react";
import {
  formatCents,
  formatPct,
  getCashSummary,
  getConcentration,
  getMetricSeries,
  getPnlSummary,
  type CashSummary,
  type ConcentrationData,
  type MetricSeriesPoint,
  type PnlSummary,
} from "@/lib/api";

function last12MonthsRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to.getFullYear() - 1, to.getMonth(), 1);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

function SeriesTable({
  title,
  points,
  isRatio,
}: {
  title: string;
  points: MetricSeriesPoint[];
  isRatio?: boolean;
}) {
  const recent = points.slice(-6);
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-text-muted">
            <th className="pb-2">Month</th>
            <th className="pb-2 text-right">Value</th>
          </tr>
        </thead>
        <tbody>
          {recent.map((p) => (
            <tr key={p.period} className="border-t border-border/60">
              <td className="py-2 text-text-muted">{p.period}</td>
              <td className="py-2 text-right tabular-nums">
                {isRatio
                  ? formatPct(p.value)
                  : formatCents(p.value_cents ?? 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConcentrationBlock({
  label,
  data,
}: {
  label: string;
  data: ConcentrationData["customers"];
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="text-sm font-semibold">{label}</h3>
      <p className="mt-1 text-xs text-text-muted">
        Top-5 share {formatPct(data.top_5_share)} · HHI {data.hhi_normalized.toFixed(3)}
      </p>
      <ul className="mt-3 space-y-2 text-sm">
        {data.top.slice(0, 5).map((row) => (
          <li key={row.name} className="flex justify-between gap-4">
            <span className="truncate text-text-muted">{row.name}</span>
            <span className="tabular-nums">
              {formatCents(row.amount_cents)} ({formatPct(row.share)})
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function FinancialsPage() {
  const [pnl, setPnl] = useState<PnlSummary | null>(null);
  const [cash, setCash] = useState<CashSummary | null>(null);
  const [concentration, setConcentration] = useState<ConcentrationData | null>(null);
  const [revenueSeries, setRevenueSeries] = useState<MetricSeriesPoint[]>([]);
  const [marginSeries, setMarginSeries] = useState<MetricSeriesPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const range = last12MonthsRange();
    Promise.all([
      getPnlSummary(range.from, range.to),
      getCashSummary(),
      getConcentration(),
      getMetricSeries("revenue"),
      getMetricSeries("gross_margin"),
    ])
      .then(([pnlData, cashData, concData, rev, gm]) => {
        setPnl(pnlData);
        setCash(cashData);
        setConcentration(concData);
        setRevenueSeries(rev);
        setMarginSeries(gm);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Financials</h1>
        <p className="text-sm text-text-muted">
          Live P&amp;L, cash, concentration, and monthly series from the financial intelligence engine.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">P&amp;L (last 12 months)</h2>
          {pnl ? (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-text-muted">Revenue</dt>
                <dd className="tabular-nums">{formatCents(pnl.revenue_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">COGS</dt>
                <dd className="tabular-nums">{formatCents(pnl.cogs_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Gross profit</dt>
                <dd className="tabular-nums">{formatCents(pnl.gross_profit_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Expenses</dt>
                <dd className="tabular-nums">{formatCents(pnl.expenses_cents)}</dd>
              </div>
              <div className="flex justify-between border-t border-border pt-2 font-semibold">
                <dt>Net profit</dt>
                <dd className="tabular-nums">{formatCents(pnl.net_profit_cents)}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-text-muted">Loading…</p>
          )}
        </div>

        <div className="rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Cash position</h2>
          {cash ? (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-text-muted">Cash</dt>
                <dd className="tabular-nums">{formatCents(cash.cash_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Net burn (3-mo)</dt>
                <dd className="tabular-nums">{formatCents(cash.net_burn_cents)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Runway</dt>
                <dd className="tabular-nums">
                  {cash.runway_months !== null ? `${cash.runway_months.toFixed(1)} mo` : "—"}
                </dd>
              </div>
              <div className="flex justify-between text-xs text-text-muted">
                <dt>As of</dt>
                <dd>{cash.as_of}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-text-muted">Loading…</p>
          )}
        </div>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        <SeriesTable title="Revenue series" points={revenueSeries} />
        <SeriesTable title="Gross margin series" points={marginSeries} isRatio />
      </section>

      {concentration && (
        <section className="mt-6 grid gap-4 md:grid-cols-2">
          <ConcentrationBlock label="Customer concentration" data={concentration.customers} />
          <ConcentrationBlock label="Vendor concentration" data={concentration.vendors} />
        </section>
      )}
    </div>
  );
}
