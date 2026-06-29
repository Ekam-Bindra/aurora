"use client";

import Link from "next/link";
import { type SimulationRecommendation } from "@/lib/api";

export default function RecommendationCard({
  rec,
  onExplain,
}: {
  rec: SimulationRecommendation;
  onExplain?: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="rounded bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted">
            P{rec.priority}
          </span>
          <h3 className="mt-1 text-sm font-medium">{rec.title}</h3>
          {rec.expected_impact && (
            <p className="mt-1 text-xs text-text-muted">
              Expected: {rec.expected_impact.magnitude}{" "}
              {rec.expected_impact.direction} on {rec.expected_impact.metric.replace(/_/g, " ")}
            </p>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href="/simulations"
          className="rounded-md border border-border px-2 py-1 text-xs text-brand-accent hover:bg-elevated"
        >
          Simulate this
        </Link>
        {onExplain && (
          <button
            type="button"
            onClick={onExplain}
            className="rounded-md border border-border px-2 py-1 text-xs text-text-muted hover:bg-elevated hover:text-text-primary"
          >
            Explain
          </button>
        )}
      </div>
    </div>
  );
}
