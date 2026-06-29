"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AgentChat from "@/components/agent/AgentChat";
import RecommendationCard from "@/components/simulation/RecommendationCard";
import { useExplain } from "@/components/explain/ExplainProvider";
import {
  formatCents,
  formatDimensionLabel,
  formatPct,
  formatYoY,
  getMe,
  getMetricsOverview,
  getRiskGenome,
  listForecasts,
  severityTone,
  type AuthUser,
  type MetricsOverviewData,
  type RiskGenomeData,
  type SimulationRecommendation,
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

function buildRecommendations(risk: RiskGenomeData | null): SimulationRecommendation[] {
  if (!risk) return [];
  const recs: SimulationRecommendation[] = [];
  let priority = 1;
  for (const dim of [...risk.dimensions].sort((a, b) => b.score - a.score)) {
    for (const action of dim.recommended_actions.slice(0, 1)) {
      recs.push({
        title: action,
        priority: priority++,
        expected_impact: {
          metric: dim.dimension,
          direction: "down",
          magnitude: `−${Math.min(dim.score * 0.1, 15).toFixed(0)} pts`,
        },
      });
    }
    if (recs.length >= 4) break;
  }
  return recs;
}

const toneClass: Record<string, string> = {
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
};

export default function OverviewPage() {
  const { openExplain } = useExplain();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [overview, setOverview] = useState<MetricsOverviewData | null>(null);
  const [risk, setRisk] = useState<RiskGenomeData | null>(null);
  const [forecastCount, setForecastCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAgent, setShowAgent] = useState(false);

  useEffect(() => {
    getMe().then(setUser).catch(() => undefined);
    getMetricsOverview()
      .then(setOverview)
      .catch((e: Error) => setError(e.message));
    getRiskGenome()
      .then(setRisk)
      .catch(() => undefined);
    listForecasts()
      .then((f) => setForecastCount(f.length))
      .catch(() => undefined);
  }, []);

  const kpis = buildKpis(overview);
  const recommendations = useMemo(() => buildRecommendations(risk), [risk]);
  const canSimulate = user?.permissions.includes("run:simulation");
  const canAgent = user?.permissions.includes("use:ai_agent");

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
              <div className="flex items-start justify-between">
                <div className="text-xs text-text-muted">{kpi.label}</div>
                <button
                  type="button"
                  onClick={() => openExplain("/explain/metric/overview")}
                  className="text-[10px] text-brand-accent hover:underline"
                >
                  Explain
                </button>
              </div>
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

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Forecasting</h2>
            <Link href="/forecasting" className="text-xs text-brand-accent hover:underline">
              Open explorer →
            </Link>
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {forecastCount !== null && forecastCount > 0
              ? `${forecastCount} forecast${forecastCount === 1 ? "" : "s"} available — view actuals with CI bands.`
              : "Generate revenue forecasts with confidence intervals."}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Risk Genome</h2>
            <Link href="/risk" className="text-xs text-brand-accent hover:underline">
              View details →
            </Link>
          </div>
          {risk ? (
            <div className="mt-2">
              <div className="text-2xl font-bold tabular-nums">
                {risk.overall_score.toFixed(1)}
                <span className="ml-2 text-sm font-normal text-text-muted">overall</span>
              </div>
              <ul className="mt-3 space-y-1 text-xs text-text-muted">
                {[...risk.dimensions]
                  .sort((a, b) => b.score - a.score)
                  .slice(0, 3)
                  .map((d) => (
                    <li key={d.dimension} className="flex justify-between">
                      <span>{formatDimensionLabel(d.dimension)}</span>
                      <span className={toneClass[severityTone(d.severity)] ?? "text-text-muted"}>
                        {d.score.toFixed(0)}
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          ) : (
            <p className="mt-2 text-sm text-text-muted">Loading risk profile…</p>
          )}
        </div>
      </section>

      {recommendations.length > 0 && (
        <section className="mt-6">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Top recommendations</h2>
            {canSimulate && (
              <Link href="/simulations" className="text-xs text-brand-accent hover:underline">
                Open simulator →
              </Link>
            )}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {recommendations.map((rec) => (
              <RecommendationCard key={rec.title} rec={rec} />
            ))}
          </div>
        </section>
      )}

      {canAgent && (
        <section className="mt-6 rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold">Ask AURORA</h2>
              <p className="mt-1 text-xs text-text-muted">
                Natural-language questions with grounded citations and tool calls.
              </p>
            </div>
            <div className="flex gap-2">
              {!showAgent && (
                <button
                  type="button"
                  onClick={() => setShowAgent(true)}
                  className="rounded-md border border-border px-3 py-1.5 text-xs text-brand-accent hover:bg-elevated"
                >
                  Ask a question
                </button>
              )}
              <Link href="/agent" className="rounded-md bg-brand-primary px-3 py-1.5 text-xs text-white">
                Full agent →
              </Link>
            </div>
          </div>
          {showAgent && (
            <div className="mt-4">
              <AgentChat compact />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
