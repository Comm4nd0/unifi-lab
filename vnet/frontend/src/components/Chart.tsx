/** Minimal SVG charts — no charting library, no runtime cost. */

import { useId } from "react";

import { cx } from "@/components/ui";
import { mbps } from "@/lib/format";

export interface Series {
  name: string;
  color: string;
  values: number[];
}

export function AreaChart({
  series,
  height = 160,
  className,
  format = mbps,
}: {
  series: Series[];
  height?: number;
  className?: string;
  format?: (value: number) => string;
}) {
  const gradientId = useId();
  const width = 600;
  const length = Math.max(...series.map((s) => s.values.length), 2);
  const peak = Math.max(1, ...series.flatMap((s) => s.values));
  // Round the ceiling up so the axis label is a number a human would pick.
  const magnitude = 10 ** Math.floor(Math.log10(peak));
  const ceiling = Math.ceil(peak / magnitude) * magnitude;

  const pointsFor = (values: number[]) =>
    values.map((value, index) => {
      const x = (index / (length - 1)) * width;
      const y = height - (value / ceiling) * (height - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

  return (
    <div className={cx("w-full", className)}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={series.map((s) => s.name).join(", ")}
      >
        <defs>
          {series.map((s, index) => (
            <linearGradient
              key={s.name}
              id={`${gradientId}-${index}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor={s.color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>

        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1="0"
            x2={width}
            y1={height * fraction}
            y2={height * fraction}
            stroke="currentColor"
            className="text-ink-800"
            strokeWidth="1"
          />
        ))}

        {series.map((s, index) => {
          const points = pointsFor(s.values);
          if (points.length < 2) return null;
          return (
            <g key={s.name}>
              <polygon
                points={`0,${height} ${points.join(" ")} ${width},${height}`}
                fill={`url(#${gradientId}-${index})`}
              />
              <polyline
                points={points.join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth="1.8"
                vectorEffect="non-scaling-stroke"
              />
            </g>
          );
        })}
      </svg>

      <div className="mt-2 flex items-center justify-between text-[11px] text-ink-500">
        <div className="flex gap-3">
          {series.map((s) => (
            <span key={s.name} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: s.color }}
              />
              {s.name}
              <span className="tabular-nums text-ink-400">
                {format(s.values.at(-1) ?? 0)}
              </span>
            </span>
          ))}
        </div>
        <span>peak {format(ceiling)}</span>
      </div>
    </div>
  );
}

export function Sparkline({
  values,
  color = "#1f7aff",
  className,
}: {
  values: number[];
  color?: string;
  className?: string;
}) {
  const peak = Math.max(1, ...values);
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 100;
      const y = 24 - (value / peak) * 22;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 24" preserveAspectRatio="none" className={cx("h-6 w-24", className)}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
