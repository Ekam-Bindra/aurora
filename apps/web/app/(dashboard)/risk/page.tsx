"use client";

import { useEffect, useState } from "react";
import RiskGenomePanel from "@/components/risk/RiskGenomePanel";
import {
  formatDimensionLabel,
  getRiskGenome,
  getRiskGenomeHistory,
  severityTone,
  type RiskGenomeData,
  type RiskGenomeHistoryEntry,
} from "@/lib/api";

const toneClass: Record<string, string> = {
  positive: "text-positive",
  warning: "text-warning",
  negative: "text-negative",
  muted: "text-text-muted",
};

export default function RiskPage() {
  const [genome, setGenome] = useState<RiskGenomeData | null>(null);
  const [history, setHistory] = useState<RiskGenomeHistoryEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getRiskGenome(), getRiskGenomeHistory()])
      .then(([g, h]) => {
        setGenome(g);
        setHistory(h);
        if (g.dimensions.length > 0) {
          const highest = [...g.dimensions].sort((a, b) => b.score - a.score)[0];
          if (highest) setSelected(highest.dimension);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Risk Genome</h1>
        <p className="text-sm text-text-muted">
          Eight-dimension enterprise risk profile with drivers and recommended actions.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      {!genome && !error ? (
        <p className="text-sm text-text-muted">Computing risk genome…</p>
      ) : genome ? (
        <>
          <RiskGenomePanel
            genome={genome}
            selectedDimension={selected}
            onSelectDimension={setSelected}
          />

          <section className="mt-6 rounded-lg border border-border bg-surface p-4">
            <h2 className="text-sm font-semibold">All dimensions</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {genome.dimensions.map((d) => {
                const tone = severityTone(d.severity);
                return (
                  <button
                    key={d.dimension}
                    type="button"
                    onClick={() => setSelected(d.dimension)}
                    className={`rounded-lg border p-3 text-left transition ${
                      selected === d.dimension
                        ? "border-brand-primary bg-brand-primary/10"
                        : "border-border hover:bg-elevated"
                    }`}
                  >
                    <div className="flex justify-between gap-2">
                      <span className="text-sm font-medium">
                        {formatDimensionLabel(d.dimension)}
                      </span>
                      <span className={`tabular-nums ${toneClass[tone]}`}>{d.score.toFixed(0)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-text-muted">{d.explanation}</p>
                  </button>
                );
              })}
            </div>
          </section>

          {history.length > 1 && (
            <section className="mt-6 rounded-lg border border-border bg-surface p-4">
              <h2 className="text-sm font-semibold">Overall score trend</h2>
              <div className="mt-3 flex items-end gap-1" style={{ height: 80 }}>
                {history.slice(-12).map((entry) => {
                  const h = Math.max(8, (entry.overall_score / 100) * 72);
                  return (
                    <div
                      key={entry.computed_at}
                      className="flex-1 rounded-t bg-brand-primary/60"
                      style={{ height: h }}
                      title={`${entry.overall_score.toFixed(1)} — ${entry.computed_at}`}
                    />
                  );
                })}
              </div>
              <p className="mt-2 text-xs text-text-muted">
                Last {Math.min(12, history.length)} compute runs
              </p>
            </section>
          )}
        </>
      ) : null}
    </div>
  );
}
