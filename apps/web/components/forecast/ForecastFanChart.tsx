"use client";

import { formatCents, type ForecastPoint, type MetricSeriesPoint } from "@/lib/api";

type ChartPoint = {
  period: string;
  actual?: number;
  yhat?: number;
  lower?: number;
  upper?: number;
  kind: "actual" | "forecast";
};

function buildChartData(
  actuals: MetricSeriesPoint[],
  forecast: ForecastPoint[],
): ChartPoint[] {
  const actualPoints: ChartPoint[] = actuals.slice(-12).map((p) => ({
    period: p.period,
    actual: p.value_cents ?? 0,
    kind: "actual",
  }));
  const forecastPoints: ChartPoint[] = forecast.map((p) => ({
    period: p.period,
    yhat: p.yhat_cents,
    lower: p.lower_cents,
    upper: p.upper_cents,
    kind: "forecast",
  }));
  return [...actualPoints, ...forecastPoints];
}

function scaleY(value: number, min: number, max: number, height: number, pad: number): number {
  if (max === min) return height / 2;
  return pad + ((max - value) / (max - min)) * (height - pad * 2);
}

function scaleX(index: number, count: number, width: number, pad: number): number {
  if (count <= 1) return width / 2;
  return pad + (index / (count - 1)) * (width - pad * 2);
}

export default function ForecastFanChart({
  actuals,
  forecast,
  height = 280,
}: {
  actuals: MetricSeriesPoint[];
  forecast: ForecastPoint[];
  height?: number;
}) {
  const data = buildChartData(actuals, forecast);
  if (data.length === 0) {
    return <p className="text-sm text-text-muted">No chart data available.</p>;
  }

  const width = 720;
  const pad = 36;
  const values = data.flatMap((d) =>
    [d.actual, d.yhat, d.lower, d.upper].filter((v): v is number => v !== undefined),
  );
  const min = Math.min(...values) * 0.92;
  const max = Math.max(...values) * 1.08;
  const firstForecastIdx = data.findIndex((d) => d.kind === "forecast");

  const bandPath = (() => {
    const upper = data
      .map((d, i) => {
        if (d.upper === undefined) return null;
        return `${i === 0 || data[i - 1]?.upper === undefined ? "M" : "L"} ${scaleX(i, data.length, width, pad)} ${scaleY(d.upper, min, max, height, pad)}`;
      })
      .filter(Boolean)
      .join(" ");
    const lower = [...data]
      .reverse()
      .map((d, revIdx) => {
        const i = data.length - 1 - revIdx;
        if (d.lower === undefined) return null;
        return `L ${scaleX(i, data.length, width, pad)} ${scaleY(d.lower, min, max, height, pad)}`;
      })
      .filter(Boolean)
      .join(" ");
    if (!upper) return "";
    return `${upper} ${lower} Z`;
  })();

  const actualLine = data
    .filter((d) => d.actual !== undefined)
    .map((d, _, arr) => {
      const i = data.indexOf(d);
      return `${arr.indexOf(d) === 0 ? "M" : "L"} ${scaleX(i, data.length, width, pad)} ${scaleY(d.actual!, min, max, height, pad)}`;
    })
    .join(" ");

  const forecastLine = data
    .filter((d) => d.yhat !== undefined)
    .map((d, idx) => {
      const i = data.indexOf(d);
      return `${idx === 0 ? "M" : "L"} ${scaleX(i, data.length, width, pad)} ${scaleY(d.yhat!, min, max, height, pad)}`;
    })
    .join(" ");

  const dividerX =
    firstForecastIdx >= 0 ? scaleX(firstForecastIdx, data.length, width, pad) : null;

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full min-w-[480px]"
        role="img"
        aria-label="Revenue forecast fan chart with confidence interval"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = pad + t * (height - pad * 2);
          const val = max - t * (max - min);
          return (
            <g key={t}>
              <line x1={pad} y1={y} x2={width - pad} y2={y} stroke="#26304A" strokeWidth={1} />
              <text x={4} y={y + 4} fill="#8A93A6" fontSize={10} className="tabular-nums">
                {formatCents(Math.round(val))}
              </text>
            </g>
          );
        })}

        {bandPath && <path d={bandPath} fill="#3B82F6" fillOpacity={0.15} stroke="none" />}
        {actualLine && (
          <path d={actualLine} fill="none" stroke="#22C55E" strokeWidth={2.5} strokeLinejoin="round" />
        )}
        {forecastLine && (
          <path
            d={forecastLine}
            fill="none"
            stroke="#3B82F6"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            strokeLinejoin="round"
          />
        )}
        {dividerX !== null && (
          <line
            x1={dividerX}
            y1={pad}
            x2={dividerX}
            y2={height - pad}
            stroke="#8A93A6"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        )}

        {data.map((d, i) =>
          i % Math.ceil(data.length / 8) === 0 || i === data.length - 1 ? (
            <text
              key={d.period}
              x={scaleX(i, data.length, width, pad)}
              y={height - 8}
              fill="#8A93A6"
              fontSize={10}
              textAnchor="middle"
            >
              {d.period.slice(0, 7)}
            </text>
          ) : null,
        )}
      </svg>

      <div className="mt-2 flex flex-wrap gap-4 text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-positive" /> Actuals
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-brand-primary" />{" "}
          Forecast
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-4 rounded-sm bg-brand-primary/20" /> 80% CI band
        </span>
      </div>
    </div>
  );
}
