"use client";

import { formatDimensionLabel, formatPct, type ExplainData } from "@/lib/api";

export default function ExplainOverlay({
  open,
  loading,
  error,
  data,
  onClose,
}: {
  open: boolean;
  loading: boolean;
  error: string | null;
  data: ExplainData | null;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="explain-title"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-border bg-elevated shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 id="explain-title" className="text-lg font-semibold">
              Explain
            </h2>
            {data && (
              <p className="text-xs capitalize text-text-muted">{data.kind} · {data.title}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-text-muted hover:bg-surface hover:text-text-primary"
            aria-label="Close explain panel"
          >
            ✕
          </button>
        </div>

        <div className="px-5 py-4">
          {loading && <p className="text-sm text-text-muted">Loading explanation…</p>}
          {error && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              {error}
            </div>
          )}
          {data && !loading && (
            <div className="space-y-4 text-sm">
              {data.formula && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Formula
                  </h3>
                  <pre className="mt-1 overflow-x-auto rounded-md bg-surface px-3 py-2 font-mono text-xs">
                    {data.formula}
                  </pre>
                </section>
              )}
              {data.method && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Method
                  </h3>
                  <p className="mt-1">{data.method}</p>
                </section>
              )}
              {data.narrative && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Summary
                  </h3>
                  <p className="mt-1 leading-relaxed">{data.narrative}</p>
                </section>
              )}
              {data.inputs && data.inputs.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Inputs
                  </h3>
                  <table className="mt-2 w-full">
                    <tbody>
                      {data.inputs.map((inp) => (
                        <tr key={inp.name} className="border-t border-border/60">
                          <td className="py-1.5 text-text-muted">{inp.name}</td>
                          <td className="py-1.5 text-right tabular-nums">{String(inp.value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}
              {data.feature_importance && data.feature_importance.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Feature importance
                  </h3>
                  <ul className="mt-2 space-y-2">
                    {[...data.feature_importance]
                      .sort((a, b) => b.importance - a.importance)
                      .map((f) => (
                        <li key={f.feature}>
                          <div className="flex justify-between text-xs">
                            <span>{formatDimensionLabel(f.feature)}</span>
                            <span className="tabular-nums">{formatPct(f.importance)}</span>
                          </div>
                          <div className="mt-1 h-1.5 rounded-full bg-surface">
                            <div
                              className="h-full rounded-full bg-brand-primary"
                              style={{ width: `${Math.min(f.importance * 100, 100)}%` }}
                            />
                          </div>
                        </li>
                      ))}
                  </ul>
                </section>
              )}
              {data.drivers && data.drivers.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Drivers
                  </h3>
                  <ul className="mt-2 space-y-2">
                    {data.drivers.map((d) => (
                      <li key={d.factor} className="flex justify-between text-xs">
                        <span>{formatDimensionLabel(d.factor)}</span>
                        <span className="tabular-nums text-text-muted">
                          {formatPct(d.contribution)} contribution
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {data.backtest && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Backtest
                  </h3>
                  <p className="mt-1 text-text-muted">
                    {data.backtest.windows} windows · MAPE {data.backtest.mape.toFixed(1)}%
                    {data.backtest.coverage_80pct != null &&
                      ` · Coverage ${(data.backtest.coverage_80pct * 100).toFixed(0)}%`}
                  </p>
                </section>
              )}
              {data.evidence && data.evidence.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Evidence
                  </h3>
                  <ul className="mt-1 space-y-1 text-xs text-brand-accent">
                    {data.evidence.map((ev) => (
                      <li key={ev.ref}>{ev.type}: {ev.ref}</li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
