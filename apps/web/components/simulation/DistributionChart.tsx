"use client";

import { formatMetricLabel } from "@/lib/api";

export default function DistributionChart({
  metric,
  histogram,
  summary,
  height = 200,
}: {
  metric: string;
  histogram?: number[];
  summary: { mean: number; p5: number; p50: number; p95: number; prob_below_3?: number };
  height?: number;
}) {
  const bins = histogram && histogram.length > 0 ? histogram : syntheticHistogram(summary);
  const maxBin = Math.max(...bins, 1);
  const width = 480;
  const pad = 24;
  const barWidth = (width - pad * 2) / bins.length;

  const isRatio = summary.mean <= 1 && summary.p95 <= 1;
  const fmt = (v: number) =>
    isRatio ? `${(v * 100).toFixed(1)}%` : v.toFixed(1);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{formatMetricLabel(metric)}</h3>
        <div className="flex flex-wrap gap-3 text-xs text-text-muted">
          <span>μ {fmt(summary.mean)}</span>
          <span>p5 {fmt(summary.p5)}</span>
          <span>p50 {fmt(summary.p50)}</span>
          <span>p95 {fmt(summary.p95)}</span>
          {summary.prob_below_3 != null && (
            <span className="text-warning">
              P(&lt;3mo) {(summary.prob_below_3 * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={`Distribution of ${metric}`}
      >
        {bins.map((count, i) => {
          const barH = (count / maxBin) * (height - pad * 2);
          const x = pad + i * barWidth;
          const y = height - pad - barH;
          return (
            <rect
              key={i}
              x={x + 1}
              y={y}
              width={Math.max(barWidth - 2, 1)}
              height={barH}
              fill="#3B82F6"
              fillOpacity={0.55 + (i / bins.length) * 0.35}
              rx={2}
            />
          );
        })}
        <line
          x1={pad}
          y1={height - pad}
          x2={width - pad}
          y2={height - pad}
          stroke="#26304A"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}

function syntheticHistogram(summary: {
  mean: number;
  p5: number;
  p50: number;
  p95: number;
}): number[] {
  const bins = 24;
  const lo = summary.p5;
  const hi = summary.p95;
  const span = hi - lo || 1;
  return Array.from({ length: bins }, (_, i) => {
    const x = lo + (i / (bins - 1)) * span;
    const dist = Math.abs(x - summary.p50) / (span / 2);
    return Math.round(Math.max(0, 100 * Math.exp(-dist * dist * 2)));
  });
}
