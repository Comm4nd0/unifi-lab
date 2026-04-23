import { profileFor, type PortKind } from "../lib/deviceModels";

type Props = {
  modelCode: string;
  /**
   * Optional per-port state override. Indexes line up with the full port
   * list (ethernet ports first, then SFP). Values: "up" | "down" |
   * "disabled" | "poe" (PoE feeding a device). Defaults to "disabled" for
   * all ports when not provided.
   */
  portStates?: ("up" | "down" | "disabled" | "poe")[];
  onPortClick?: (index: number) => void;
};

const PORT_W = 36;
const PORT_H = 22;
const GAP_X = 6;
const GAP_Y = 10;
const ROW_COUNT = 2;

const STATE_FILL: Record<string, string> = {
  up: "#059669", // emerald-600
  down: "#64748b", // slate-500
  disabled: "#334155", // slate-700
  poe: "#f59e0b", // amber-500
};

const KIND_LABEL: Record<PortKind, string> = {
  ethernet: "RJ45",
  sfp: "SFP",
  "sfp+": "SFP+",
  console: "CON",
};

export function PortMap({ modelCode, portStates, onPortClick }: Props) {
  const profile = profileFor(modelCode);
  if (!profile.ports || profile.ports.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No physical port layout for <span className="font-mono">{modelCode}</span>.
      </p>
    );
  }

  // Expand the port groups into a flat list of { kind, poe } entries.
  const ports: { kind: PortKind; poe: boolean }[] = [];
  for (const group of profile.ports) {
    for (let i = 0; i < group.count; i++) {
      ports.push({ kind: group.kind, poe: !!group.poe });
    }
  }

  const ethCount = ports.filter((p) => p.kind === "ethernet").length;
  const sfpCount = ports.length - ethCount;
  const perRowEth = Math.ceil(ethCount / ROW_COUNT);
  const svgWidth = perRowEth * (PORT_W + GAP_X) + sfpCount * (PORT_W + GAP_X) + 40;
  const svgHeight = ROW_COUNT * (PORT_H + GAP_Y) + 40;

  return (
    <div className="overflow-x-auto">
      <svg
        width={svgWidth}
        height={svgHeight}
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="rounded-md border border-slate-800 bg-slate-950 p-2"
        role="img"
        aria-label={`${modelCode} port map`}
      >
        {ports.map((port, idx) => {
          const state = portStates?.[idx] ?? "disabled";
          const fill = STATE_FILL[state] ?? STATE_FILL.disabled;

          let col: number;
          let row: number;
          if (port.kind === "ethernet") {
            col = idx % perRowEth;
            row = Math.floor(idx / perRowEth);
          } else {
            const sfpIdx = idx - ethCount;
            col = perRowEth + sfpIdx;
            row = 0;
          }

          const x = 20 + col * (PORT_W + GAP_X);
          const y = 20 + row * (PORT_H + GAP_Y);
          const label = port.kind === "ethernet" ? idx + 1 : KIND_LABEL[port.kind];

          return (
            <g
              key={idx}
              onClick={onPortClick ? () => onPortClick(idx) : undefined}
              style={{ cursor: onPortClick ? "pointer" : "default" }}
            >
              <title>
                {`Port ${idx + 1} · ${port.kind.toUpperCase()}${port.poe ? " · PoE" : ""} · ${state}`}
              </title>
              <rect
                x={x}
                y={y}
                width={PORT_W}
                height={PORT_H}
                rx={3}
                fill={fill}
                stroke="#0f172a"
                strokeWidth={1}
              />
              <text
                x={x + PORT_W / 2}
                y={y + PORT_H / 2 + 4}
                textAnchor="middle"
                fontSize={10}
                fontFamily="ui-monospace, monospace"
                fill="#e2e8f0"
              >
                {label}
              </text>
              {port.poe && (
                <circle cx={x + PORT_W - 4} cy={y + 4} r={2} fill="#fbbf24" />
              )}
            </g>
          );
        })}
      </svg>
      <LegendRow />
    </div>
  );
}

function LegendRow() {
  return (
    <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-400">
      {(Object.keys(STATE_FILL) as (keyof typeof STATE_FILL)[]).map((s) => (
        <div key={s} className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded"
            style={{ backgroundColor: STATE_FILL[s] }}
          />
          <span className="capitalize">{s}</span>
        </div>
      ))}
      <div className="flex items-center gap-1">
        <span className="inline-block h-2 w-2 rounded-full bg-amber-400" />
        <span>PoE capable</span>
      </div>
    </div>
  );
}
