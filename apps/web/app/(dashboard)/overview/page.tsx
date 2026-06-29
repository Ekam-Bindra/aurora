"use client";

import { useEffect, useState } from "react";
import { getMe, type AuthUser } from "@/lib/api";

type Kpi = { label: string; value: string; delta?: string; tone?: "positive" | "negative" | "warning" };

// Placeholder figures matching the demo narrative. Wired to GET /metrics/overview in Phase 3.
const KPIS: Kpi[] = [
  { label: "Revenue (MTD)", value: "$51.2M", delta: "+17.4% YoY", tone: "positive" },
  { label: "Gross Margin", value: "41.2%", delta: "+2.1 pts", tone: "positive" },
  { label: "Operating Margin", value: "8.9%", delta: "-1.3 pts", tone: "warning" },
  { label: "Net Burn", value: "$4.2M", delta: "trailing 3-mo" },
  { label: "Cash Runway", value: "5.4 mo", delta: "trending down", tone: "negative" },
  { label: "Overall Risk", value: "58 / 100", delta: "elevated", tone: "warning" },
];

const toneClass: Record<string, string> = {
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
};

export default function OverviewPage() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    getMe().then(setUser).catch(() => undefined);
  }, []);

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Executive Dashboard</h1>
        <p className="text-sm text-text-muted">
          {user ? `Welcome, ${user.full_name} · ${user.title}` : "Loading…"}
        </p>
      </header>

      <section className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {KPIS.map((kpi) => (
          <div key={kpi.label} className="rounded-lg border border-border bg-surface p-4">
            <div className="text-xs text-text-muted">{kpi.label}</div>
            <div className="mt-1 text-2xl font-bold tabular-nums">{kpi.value}</div>
            {kpi.delta && (
              <div className={`mt-1 text-xs ${kpi.tone ? toneClass[kpi.tone] : "text-text-muted"}`}>
                {kpi.delta}
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="mt-8 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold">Phase 1 — Foundation</h2>
        <p className="mt-2 text-sm text-text-muted">
          Authentication, RBAC, multi-tenancy, and the application shell are in place. The KPI
          values above are placeholders; they are wired to the live Financial Intelligence engine
          in Phase 3, with the forecast, risk genome, simulator, and AI agent following per the{" "}
          <span className="text-text-primary">implementation roadmap</span>.
        </p>
        {user && (
          <p className="mt-3 text-xs text-text-muted">
            Your permissions: <span className="text-text-primary">{user.permissions.join(", ")}</span>
          </p>
        )}
      </section>
    </div>
  );
}
