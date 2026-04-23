import type { FlowStats } from "../api/client";

/** Compact stacked-bar sparkline for flow rate over time.
 *
 * One bar per bucket; allowed (emerald) stacked below blocked (rose).
 * Pure SVG — no chart lib, keeps the bundle lean. Renders even when
 * every bucket is zero so the chart frame stays stable during live
 * refreshes.
 */
export function FlowRateChart({
  stats,
  height = 72,
  className,
}: {
  stats: FlowStats;
  height?: number;
  className?: string;
}) {
  const buckets = stats.buckets;
  const maxCount = Math.max(1, ...buckets.map((b) => b.allowed + b.blocked));
  const gap = 1;
  const viewW = Math.max(100, buckets.length * 6);
  const barW = Math.max(1, (viewW - gap * (buckets.length - 1)) / Math.max(1, buckets.length));

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${viewW} ${height}`}
        preserveAspectRatio="none"
        className="block h-full w-full"
        role="img"
        aria-label="Flow rate per bucket"
      >
        {buckets.map((b, i) => {
          const total = b.allowed + b.blocked;
          const totalH = (total / maxCount) * (height - 2);
          const allowedH = total === 0 ? 0 : (b.allowed / total) * totalH;
          const blockedH = totalH - allowedH;
          const x = i * (barW + gap);
          return (
            <g key={b.t}>
              {/* Allowed on the bottom. */}
              <rect
                x={x}
                y={height - allowedH}
                width={barW}
                height={allowedH}
                className="fill-emerald-500/80"
              >
                <title>
                  {new Date(b.t).toLocaleTimeString()} · {b.allowed} allowed / {b.blocked} blocked
                </title>
              </rect>
              {/* Blocked stacks on top. */}
              <rect
                x={x}
                y={height - allowedH - blockedH}
                width={barW}
                height={blockedH}
                className="fill-rose-500/80"
              >
                <title>
                  {new Date(b.t).toLocaleTimeString()} · {b.allowed} allowed / {b.blocked} blocked
                </title>
              </rect>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex items-center justify-between text-[10px] uppercase tracking-wide text-slate-500">
        <span>{new Date(stats.start).toLocaleTimeString()}</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/80" />
            allowed
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-rose-500/80" />
            blocked
          </span>
        </span>
        <span>now</span>
      </div>
    </div>
  );
}
