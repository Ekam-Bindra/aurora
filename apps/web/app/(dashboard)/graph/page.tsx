"use client";

import { useEffect, useState } from "react";
import GraphExplorer from "@/components/graph/GraphExplorer";
import {
  formatCents,
  formatPct,
  getGraphImpact,
  getGraphNodes,
  type GraphNode,
} from "@/lib/api";

type ViewMode = "neighborhood" | "impact";

export default function GraphPage() {
  const [vendors, setVendors] = useState<GraphNode[]>([]);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [mode, setMode] = useState<ViewMode>("impact");
  const [impact, setImpact] = useState<Awaited<ReturnType<typeof getGraphImpact>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGraphNodes("Vendor")
      .then((nodes) => {
        setVendors(nodes);
        const critical = nodes.find((n) => n.criticality === "critical") ?? nodes[0];
        if (critical) setSelected(critical);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getGraphImpact(selected.id, 2)
      .then(setImpact)
      .catch((e: Error) => setError(e.message));
  }, [selected]);

  return (
    <div className="p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Knowledge Graph</h1>
          <p className="text-sm text-text-muted">
            Relationship map and vendor impact analysis — synced from the Nimbus tenant database.
          </p>
        </div>
        <div className="flex rounded-lg border border-border bg-surface p-1 text-sm">
          {(["impact", "neighborhood"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded px-3 py-1 capitalize ${
                mode === m ? "bg-elevated text-text-primary" : "text-text-muted"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <section className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-surface p-4 lg:col-span-1">
          <h2 className="text-sm font-semibold">Vendors</h2>
          <ul className="mt-3 max-h-[420px] space-y-2 overflow-y-auto text-sm">
            {vendors.map((v) => (
              <li key={v.id}>
                <button
                  type="button"
                  onClick={() => setSelected(v)}
                  className={`w-full rounded px-2 py-1 text-left ${
                    selected?.id === v.id ? "bg-elevated text-text-primary" : "text-text-muted"
                  }`}
                >
                  {v.name}
                  {v.criticality === "critical" && (
                    <span className="ml-2 text-xs text-warning">critical</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-border bg-surface p-4 lg:col-span-3">
          <h2 className="mb-3 text-sm font-semibold">
            Graph explorer
            {selected && (
              <span className="ml-2 font-normal text-text-muted">— {selected.name}</span>
            )}
          </h2>
          {selected ? (
            <GraphExplorer rootNode={selected} mode={mode} depth={2} onNodeSelect={setSelected} />
          ) : (
            <p className="text-sm text-text-muted">Select a vendor to explore the graph.</p>
          )}
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Impact analysis</h2>
          {selected && impact ? (
            <div className="mt-3 space-y-4 text-sm">
              <p>
                Selected: <span className="font-medium">{impact.node?.name}</span>
                {impact.node?.criticality && (
                  <span className="ml-2 text-text-muted">({impact.node.criticality})</span>
                )}
              </p>
              <p className="text-text-muted">
                Estimated revenue at risk:{" "}
                <span className="tabular-nums text-text-primary">
                  {formatCents(impact.impact.estimated_revenue_at_risk_cents)}
                </span>
              </p>

              <div>
                <h3 className="font-medium">Affected products</h3>
                <ul className="mt-1 text-text-muted">
                  {impact.impact.affected_products.map((p) => (
                    <li key={p.id}>{p.name}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="font-medium">Affected customers</h3>
                <ul className="mt-1 text-text-muted">
                  {impact.impact.affected_customers.slice(0, 8).map((c) => (
                    <li key={c.id}>
                      {c.name}
                      {c.revenue_share !== undefined && (
                        <span className="ml-2 tabular-nums">
                          ({formatPct(c.revenue_share)})
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>

              {impact.impact.affected_departments.length > 0 && (
                <div>
                  <h3 className="font-medium">Dependent departments</h3>
                  <ul className="mt-1 text-text-muted">
                    {impact.impact.affected_departments.map((d) => (
                      <li key={d.id}>{d.name}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="mt-3 text-sm text-text-muted">Loading impact…</p>
          )}
        </div>

        <div className="rounded-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Demo dependency chain</h2>
          <p className="mt-2 text-sm text-text-muted">
            The Nimbus demo wires a critical vendor through product lines to top customers,
            projects, and key engineers — visible in impact mode for{" "}
            <span className="text-text-primary">Vanguard Freight Co.</span>
          </p>
          <ul className="mt-3 space-y-1 text-sm text-text-muted">
            <li>→ Electronics Accessories product line</li>
            <li>→ Continental Mercantile Group (~14% revenue)</li>
            <li>→ Key Account Fulfillment project</li>
            <li>→ Supply Chain department dependency</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
