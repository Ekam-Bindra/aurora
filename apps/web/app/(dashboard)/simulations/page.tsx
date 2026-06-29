"use client";

import { useCallback, useEffect, useState } from "react";
import DistributionChart from "@/components/simulation/DistributionChart";
import RecommendationCard from "@/components/simulation/RecommendationCard";
import { useExplain } from "@/components/explain/ExplainProvider";
import {
  createScenario,
  formatDimensionLabel,
  formatMetricLabel,
  getGraphNodes,
  getSimulation,
  runScenario,
  type GraphNode,
  type ScenarioShock,
  type SimulationData,
} from "@/lib/api";

type ShockDraft =
  | { type: "customer_churn"; customer_id: string; probability: number }
  | { type: "expense_change"; category: string; department_code: string; pct_change: number };

const DEFAULT_EXPENSE_SHOCK: ShockDraft = {
  type: "expense_change",
  category: "payroll",
  department_code: "ENG",
  pct_change: 0.06,
};

export default function SimulationsPage() {
  const { openExplain } = useExplain();
  const [name, setName] = useState("Lose top customer + 6% eng raise");
  const [horizon, setHorizon] = useState(12);
  const [trials, setTrials] = useState(10000);
  const [shocks, setShocks] = useState<ShockDraft[]>([
    { type: "customer_churn", customer_id: "", probability: 1.0 },
  ]);
  const [customers, setCustomers] = useState<GraphNode[]>([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [result, setResult] = useState<SimulationData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGraphNodes("Customer")
      .then((nodes) => {
        setCustomers(nodes);
        if (nodes.length > 0) {
          setShocks((prev) =>
            prev.map((s) =>
              s.type === "customer_churn" && !s.customer_id
                ? { ...s, customer_id: nodes[0]!.id }
                : s,
            ),
          );
        }
      })
      .catch(() => undefined);
  }, []);

  const addShock = (type: ShockDraft["type"]) => {
    if (type === "customer_churn") {
      setShocks((prev) => [
        ...prev,
        {
          type: "customer_churn",
          customer_id: customers[0]?.id ?? "",
          probability: 1.0,
        },
      ]);
    } else {
      setShocks((prev) => [...prev, { ...DEFAULT_EXPENSE_SHOCK }]);
    }
  };

  const removeShock = (index: number) => {
    setShocks((prev) => prev.filter((_, i) => i !== index));
  };

  const updateShock = (index: number, patch: Partial<ShockDraft>) => {
    setShocks((prev) =>
      prev.map((s, i) => (i === index ? ({ ...s, ...patch } as ShockDraft) : s)),
    );
  };

  const pollSimulation = useCallback(async (simId: string) => {
    for (let attempt = 0; attempt < 60; attempt++) {
      const sim = await getSimulation(simId);
      if (sim.status === "completed") {
        setResult(sim);
        setProgress(100);
        return;
      }
      if (sim.status === "failed") {
        throw new Error("Simulation failed");
      }
      setProgress(Math.min(95, 10 + attempt * 3));
      await new Promise((r) => setTimeout(r, 800));
    }
    throw new Error("Simulation timed out");
  }, []);

  const onRun = async () => {
    if (shocks.length === 0) {
      setError("Add at least one shock");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    setProgress(0);

    try {
      const apiShocks: ScenarioShock[] = shocks.map((s) => {
        if (s.type === "customer_churn") {
          return {
            type: "customer_churn",
            customer_id: s.customer_id,
            probability: s.probability,
          };
        }
        return {
          type: "expense_change",
          category: s.category,
          department_code: s.department_code,
          pct_change: s.pct_change,
        };
      });

      const created = await createScenario({
        name,
        horizon_periods: horizon,
        trials,
        assumptions: { shocks: apiShocks },
      });

      setProgress(5);
      const launched = await runScenario(created.id);
      setProgress(10);
      await pollSimulation(launched.simulation_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Scenario Simulator</h1>
        <p className="text-sm text-text-muted">
          Monte Carlo what-if analysis — configure shocks, run trials, review distributions and
          recommendations.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold">Scenario builder</h2>

          <label className="mt-4 block text-sm">
            <span className="text-text-muted">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
            />
          </label>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="text-text-muted">Horizon (mo)</span>
              <input
                type="number"
                min={1}
                max={36}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm tabular-nums"
              />
            </label>
            <label className="text-sm">
              <span className="text-text-muted">Trials</span>
              <input
                type="number"
                min={1000}
                step={1000}
                value={trials}
                onChange={(e) => setTrials(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm tabular-nums"
              />
            </label>
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Shocks
              </h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => addShock("customer_churn")}
                  className="text-xs text-brand-accent hover:underline"
                >
                  + Customer churn
                </button>
                <button
                  type="button"
                  onClick={() => addShock("expense_change")}
                  className="text-xs text-brand-accent hover:underline"
                >
                  + Expense change
                </button>
              </div>
            </div>

            <div className="mt-3 space-y-3">
              {shocks.map((shock, i) => (
                <div key={i} className="rounded-md border border-border bg-elevated p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium capitalize">
                      {shock.type.replace("_", " ")}
                    </span>
                    {shocks.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeShock(i)}
                        className="text-xs text-text-muted hover:text-negative"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  {shock.type === "customer_churn" ? (
                    <div className="mt-2 space-y-2">
                      <label className="block text-xs">
                        <span className="text-text-muted">Customer</span>
                        <select
                          value={shock.customer_id}
                          onChange={(e) => updateShock(i, { customer_id: e.target.value })}
                          className="mt-1 w-full rounded border border-border bg-surface px-2 py-1 text-sm"
                        >
                          {customers.length === 0 && (
                            <option value="">Loading customers…</option>
                          )}
                          {customers.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs">
                        <span className="text-text-muted">Probability</span>
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={shock.probability}
                          onChange={(e) =>
                            updateShock(i, { probability: Number(e.target.value) })
                          }
                          className="mt-1 w-full rounded border border-border bg-surface px-2 py-1 text-sm tabular-nums"
                        />
                      </label>
                    </div>
                  ) : (
                    <div className="mt-2 grid grid-cols-3 gap-2">
                      <label className="text-xs">
                        <span className="text-text-muted">Category</span>
                        <input
                          type="text"
                          value={shock.category}
                          onChange={(e) => updateShock(i, { category: e.target.value })}
                          className="mt-1 w-full rounded border border-border bg-surface px-2 py-1 text-sm"
                        />
                      </label>
                      <label className="text-xs">
                        <span className="text-text-muted">Dept</span>
                        <input
                          type="text"
                          value={shock.department_code}
                          onChange={(e) => updateShock(i, { department_code: e.target.value })}
                          className="mt-1 w-full rounded border border-border bg-surface px-2 py-1 text-sm"
                        />
                      </label>
                      <label className="text-xs">
                        <span className="text-text-muted">% change</span>
                        <input
                          type="number"
                          step={0.01}
                          value={shock.pct_change}
                          onChange={(e) =>
                            updateShock(i, { pct_change: Number(e.target.value) })
                          }
                          className="mt-1 w-full rounded border border-border bg-surface px-2 py-1 text-sm tabular-nums"
                        />
                      </label>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={onRun}
            disabled={running}
            className="mt-5 w-full rounded-md bg-brand-primary py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {running ? `Running… ${progress ?? 0}%` : "Run simulation"}
          </button>

          {running && progress !== null && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-elevated">
              <div
                className="h-full bg-brand-primary transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </section>

        <section className="rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Results</h2>
            {result?.explain_ref && (
              <button
                type="button"
                onClick={() => openExplain(result.explain_ref!)}
                className="text-xs text-brand-accent hover:underline"
              >
                Explain
              </button>
            )}
          </div>

          {!result && !running && (
            <p className="mt-4 text-sm text-text-muted">
              Configure shocks and run a simulation to see outcome distributions.
            </p>
          )}

          {result && (
            <div className="mt-4 space-y-6">
              {result.results.map((r) => (
                <DistributionChart
                  key={r.metric}
                  metric={r.metric}
                  histogram={r.histogram}
                  summary={r.summary}
                />
              ))}

              {Object.keys(result.risk_deltas).length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Risk deltas
                  </h3>
                  <ul className="mt-2 space-y-1 text-sm">
                    {Object.entries(result.risk_deltas).map(([dim, delta]) => (
                      <li key={dim} className="flex justify-between">
                        <span>{formatDimensionLabel(dim)}</span>
                        <span
                          className={`tabular-nums ${delta > 0 ? "text-negative" : delta < 0 ? "text-positive" : "text-text-muted"}`}
                        >
                          {delta > 0 ? "+" : ""}
                          {delta.toFixed(1)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.recommendations.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Recommendations
                  </h3>
                  <div className="mt-3 space-y-3">
                    {result.recommendations
                      .sort((a, b) => a.priority - b.priority)
                      .map((rec) => (
                        <RecommendationCard
                          key={rec.title}
                          rec={rec}
                          onExplain={
                            result.explain_ref
                              ? () => openExplain(result.explain_ref!)
                              : undefined
                          }
                        />
                      ))}
                  </div>
                </div>
              )}

              <p className="text-xs text-text-muted">
                {result.trials.toLocaleString()} trials · status {result.status} ·{" "}
                {formatMetricLabel(result.id)}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
