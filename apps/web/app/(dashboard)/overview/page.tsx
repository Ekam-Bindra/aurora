"use client";

import { useEffect, useState } from "react";
import {
  formatCents,
  formatPct,
  formatYoY,
  getMe,
  getMetricsOverview,
  type AuthUser,
  type MetricsOverviewData,
} from "@/lib/api";

type Kpi = { label: string; value: string; delta?: string; tone?: "positive" | "negative" | "warning" };

function toneFromDelta(delta: number | null | undefined): Kpi["tone"] {
  if (delta === null || delta === undefined) return undefined;
  if (delta > 0) return "positive";
  if (delta < 0) return "negative";
  return undefined;
}

function toneFromRunway(months: number | undefined, trend?: string): Kpi["tone"] {
  if (trend === "down" || (months !== undefined && months < 6)) return "negative";
  if (months !== undefined && months < 9) return "warning";
  return "positive";
}

function buildKpis(data: MetricsOverviewData | null): Kpi[] {
  if (!data?.kpis) return [];

  const kpis = data.kpis;
  const items: Kpi[] = [];

  if (kpis.revenue_mtd) {
    items.push({
      label: "Revenue (MTD)",
      value: formatCents(kpis.revenue_mtd.value_cents),
      delta: formatYoY(kpis.revenue_mtd.delta_pct_yoy),
      tone: toneFromDelta(kpis.revenue_mtd.delta_pct_yoy),
    });
  }
  if (kpis.gross_margin) {
    items.push({
      label: "Gross Margin",
      value: formatPct(kpis.gross_margin.value),
      delta: formatYoY(kpis.gross_margin.delta_pct_yoy),
      tone: toneFromDelta(kpis.gross_margin.delta_pct_yoy),
    });
  }
  if (kpis.operating_margin) {
    items.push({
      label: "Operating Margin",
      value: formatPct(kpis.operating_margin.value),
      delta: formatYoY(kpis.operating_margin.delta_pct_yoy),
      tone: toneFromDelta(kpis.operating_margin.delta_pct_yoy),
    });
  }
  if (kpis.net_burn) {
    items.push({
      label: "Net Burn",
      value: formatCents(kpis.net_burn.value_cents),
      delta: "trailing 3-mo",
    });
  }
  if (kpis.cash_runway_months) {
    const months = kpis.cash_runway_months.value;
    items.push({
      label: "Cash Runway",
      value: months >= 999 ? "∞" : `${months.toFixed(1)} mo`,
      delta: kpis.cash_runway_months.trend === "down" ? "trending down" : "stable",
      tone: toneFromRunway(months, kpis.cash_runway_months.trend),
    });
  }

  return items;
}

const toneClass: Record<string, string> = {
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
};

export default function OverviewPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [overview, setOverview] = useState<MetricsOverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe().then(setUser).catch(() => undefined);
    getMetricsOverview()
      .then(setOverview)
      .catch((e: Error) => setError(e.message));
  }, []);

  const kpis = buildKpis(overview);

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Executive Dashboard</h1>
        <p className="text-sm text-text-muted">
          {user ? `Welcome, ${user.full_name} · ${user.title}` : "Loading…"}
          {overview?.as_of && (
            <span className="ml-2 text-text-muted">· as of {overview.as_of}</span>
          )}
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <section className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {kpis.length === 0 && !error ? (
          <p className="text-sm text-text-muted">Loading KPIs…</p>
        ) : (
          kpis.map((kpi) => (
            <div key={kpi.label} className="rounded-lg border border-border bg-surface p-4">
              <div className="text-xs text-text-muted">{kpi.label}</div>
              <div className="mt-1 text-2xl font-bold tabular-nums">{kpi.value}</div>
              {kpi.delta && (
                <div className={`mt-1 text-xs ${kpi.tone ? toneClass[kpi.tone] : "text-text-muted"}`}>
                  {kpi.delta}
                </div>
              )}
            </div>
          ))
        )}
      </section>

      <section className="mt-8 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold">Phase 3 — Financial Intelligence</h2>
        <p className="mt-2 text-sm text-text-muted">
          KPIs above are computed live from the Nimbus demo tenant via DuckDB marts and the
          financial engine in <span className="text-text-primary">packages/ml</span>. Forecasting,
          risk genome, simulator, and AI agent follow per the implementation roadmap.
        </p>
        {user && (
          <p className="mt-3 text-xs text-text-muted">
            Your permissions:{" "}
            <span className="text-text-primary">{user.permissions.join(", ")}</span>
          </p>
        )}
      </section>
    </div>
  );
}
