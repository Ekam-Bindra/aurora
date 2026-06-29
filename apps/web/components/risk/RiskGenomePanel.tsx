"use client";

import {
  formatDimensionLabel,
  severityTone,
  type RiskDimension,
  type RiskGenomeData,
} from "@/lib/api";

const toneClass: Record<string, string> = {
  positive: "text-positive",
  warning: "text-warning",
  negative: "text-negative",
  muted: "text-text-muted",
};

const severityBg: Record<string, string> = {
  low: "bg-positive/15 border-positive/30",
  moderate: "bg-brand-primary/10 border-brand-primary/30",
  high: "bg-warning/15 border-warning/40",
  critical: "bg-negative/15 border-negative/40",
};

function RadarChart({ dimensions }: { dimensions: RiskDimension[] }) {
  const size = 280;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 100;
  const n = dimensions.length;

  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;

  const point = (i: number, score: number) => {
    const r = (score / 100) * radius;
    return {
      x: cx + r * Math.cos(angle(i)),
      y: cy + r * Math.sin(angle(i)),
    };
  };

  const gridLevels = [25, 50, 75, 100];
  const dataPath = dimensions
    .map((d, i) => {
      const p = point(i, d.score);
      return `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-[320px]" role="img" aria-label="Risk genome radar chart">
      {gridLevels.map((level) => (
        <polygon
          key={level}
          points={dimensions
            .map((_, i) => {
              const p = point(i, level);
              return `${p.x},${p.y}`;
            })
            .join(" ")}
          fill="none"
          stroke="#26304A"
          strokeWidth={1}
        />
      ))}

      {dimensions.map((d, i) => {
        const outer = point(i, 100);
        return (
          <line key={d.dimension} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="#26304A" strokeWidth={1} />
        );
      })}

      <path d={`${dataPath} Z`} fill="#3B82F6" fillOpacity={0.2} stroke="#3B82F6" strokeWidth={2} />

      {dimensions.map((d, i) => {
        const label = point(i, 118);
        return (
          <text
            key={d.dimension}
            x={label.x}
            y={label.y}
            fill="#8A93A6"
            fontSize={9}
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {formatDimensionLabel(d.dimension).split(" ")[0]}
          </text>
        );
      })}
    </svg>
  );
}

function GaugeBar({ dimension, selected, onSelect }: {
  dimension: RiskDimension;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = severityTone(dimension.severity);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-3 text-left transition ${
        selected ? "border-brand-primary bg-brand-primary/10" : "border-border bg-elevated/40 hover:bg-elevated"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-text-muted">{formatDimensionLabel(dimension.dimension)}</span>
        <span className={`text-sm font-semibold tabular-nums ${toneClass[tone]}`}>
          {dimension.score.toFixed(0)}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border">
        <div
          className={`h-full rounded-full ${
            tone === "positive"
              ? "bg-positive"
              : tone === "negative"
                ? "bg-negative"
                : "bg-warning"
          }`}
          style={{ width: `${Math.min(100, dimension.score)}%` }}
        />
      </div>
      <span className={`mt-1 inline-block text-[10px] capitalize ${toneClass[tone]}`}>
        {dimension.severity}
      </span>
    </button>
  );
}

function DimensionDetail({ dimension }: { dimension: RiskDimension }) {
  const tone = severityTone(dimension.severity);
  return (
    <div className={`rounded-lg border p-4 ${severityBg[dimension.severity] ?? "border-border bg-surface"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{formatDimensionLabel(dimension.dimension)}</h3>
        <span className={`text-lg font-bold tabular-nums ${toneClass[tone]}`}>
          {dimension.score.toFixed(1)}
          <span className="ml-1 text-xs font-normal capitalize">({dimension.severity})</span>
        </span>
      </div>

      <p className="mt-3 text-sm text-text-muted">{dimension.explanation}</p>

      {dimension.drivers.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Drivers</h4>
          <ul className="mt-2 space-y-2">
            {dimension.drivers.map((dr) => (
              <li key={dr.factor} className="text-sm">
                <div className="flex justify-between gap-2">
                  <span className="text-text-muted">{dr.factor.replace(/_/g, " ")}</span>
                  <span className="tabular-nums text-text-primary">
                    {(dr.contribution * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="mt-1 h-1 overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full rounded-full bg-brand-primary"
                    style={{ width: `${Math.min(100, dr.contribution * 100)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {dimension.recommended_actions.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Recommended actions
          </h4>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-text-primary">
            {dimension.recommended_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function RiskGenomePanel({
  genome,
  selectedDimension,
  onSelectDimension,
}: {
  genome: RiskGenomeData;
  selectedDimension: string | null;
  onSelectDimension: (dimension: string) => void;
}) {
  const active =
    genome.dimensions.find((d) => d.dimension === selectedDimension) ?? genome.dimensions[0];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="rounded-lg border border-border bg-surface p-4 lg:col-span-1">
        <div className="text-center">
          <div className="text-xs text-text-muted">Overall risk score</div>
          <div className="mt-1 text-4xl font-bold tabular-nums text-text-primary">
            {genome.overall_score.toFixed(1)}
          </div>
          <div className="text-xs text-text-muted">Computed {new Date(genome.computed_at).toLocaleString()}</div>
        </div>
        <RadarChart dimensions={genome.dimensions} />
      </div>

      <div className="lg:col-span-2">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {genome.dimensions.map((d) => (
            <GaugeBar
              key={d.dimension}
              dimension={d}
              selected={active?.dimension === d.dimension}
              onSelect={() => onSelectDimension(d.dimension)}
            />
          ))}
        </div>

        {active && (
          <div className="mt-4">
            <DimensionDetail dimension={active} />
          </div>
        )}
      </div>
    </div>
  );
}
