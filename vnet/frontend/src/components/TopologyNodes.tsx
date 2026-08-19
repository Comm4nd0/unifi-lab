/** Custom React Flow nodes: a device with a live, connectable port strip. */

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { portTone } from "@/components/PortGrid";
import { BoltIcon, CloudIcon, LINE_ICONS } from "@/components/icons";
import { StatusDot, cx } from "@/components/ui";
import { mbps, speed } from "@/lib/format";
import type { SimDevice, SimPort } from "@/types";

export interface DeviceNodeData extends Record<string, unknown> {
  device: SimDevice;
  isRoot: boolean;
}

const HANDLE_STYLE: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  width: "100%",
  height: "100%",
  minWidth: 0,
  minHeight: 0,
  transform: "none",
  background: "transparent",
  border: "none",
  borderRadius: 4,
};

export function DeviceNode({ data, selected }: NodeProps) {
  const { device, isRoot } = data as unknown as DeviceNodeData;
  const Icon = LINE_ICONS[device.line] ?? LINE_ICONS.other;
  const copper = device.ports.filter((port) => port.media === "rj45");
  const fibre = device.ports.filter((port) => port.media !== "rj45");

  return (
    <div
      className={cx(
        "w-[236px] rounded-lg border bg-ink-900 shadow-panel transition",
        device.status === "offline"
          ? "border-ink-700 opacity-60"
          : device.status === "error"
            ? "border-bad/60"
            : "border-ink-700",
        selected && "border-unifi-bright ring-2 ring-unifi/40",
      )}
    >
      <div className="flex items-start gap-2 px-3 py-2">
        <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded bg-ink-800 text-unifi-bright">
          <Icon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <StatusDot status={device.status} />
            <span className="truncate text-xs font-semibold text-ink-100">{device.name}</span>
          </div>
          <div className="truncate text-[10px] text-ink-500">{device.short}</div>
        </div>
        {isRoot && (
          <span className="rounded bg-unifi/20 px-1 py-0.5 text-[9px] font-semibold text-unifi-bright">
            ROOT
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-start gap-2 border-t border-ink-800 px-3 py-2">
        {copper.length > 0 && (
          <div className={cx("grid gap-[3px]", copper.length > 8 ? "grid-flow-col grid-rows-2" : "grid-flow-col")}>
            {copper.map((port) => (
              <PortHandle key={port.id} port={port} />
            ))}
          </div>
        )}
        {fibre.length > 0 && (
          <div className="grid grid-flow-col gap-[3px] border-l border-ink-800 pl-2">
            {fibre.map((port) => (
              <PortHandle key={port.id} port={port} fibre />
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-ink-800 px-3 py-1.5 text-[10px] text-ink-500">
        <span className="tabular-nums">{mbps(device.throughput_mbps)}</span>
        <span>
          {device.client_count > 0 &&
            `${device.client_count} client${device.client_count === 1 ? "" : "s"}`}
          {device.poe_budget_w > 0 && device.client_count > 0 && " · "}
          {device.poe_budget_w > 0 && `${device.poe_used_w.toFixed(0)}W PoE`}
        </span>
      </div>
    </div>
  );
}

function PortHandle({ port, fibre }: { port: SimPort; fibre?: boolean }) {
  const tone = portTone(port);
  return (
    <div
      className={cx(
        "relative grid h-4 w-4 place-items-center border text-[7px] font-bold leading-none",
        fibre ? "rounded-[2px]" : "rounded-sm",
        tone.className,
      )}
      title={`${port.label} · ${tone.label}${port.speed_mbps ? ` · ${speed(port.speed_mbps)}` : ""}`}
    >
      {port.role === "wan" ? "W" : port.index}
      {port.poe_delivered_w > 0 && (
        <BoltIcon size={6} className="absolute -right-1 -top-1 text-warn" strokeWidth={4} />
      )}
      <Handle type="source" id={port.id} position={Position.Bottom} style={HANDLE_STYLE} />
    </div>
  );
}

export function InternetNode() {
  return (
    <div className="flex w-[150px] items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2">
      <CloudIcon size={20} className="text-ink-400" />
      <div>
        <div className="text-xs font-semibold text-ink-200">Internet</div>
        <div className="text-[10px] text-ink-500">WAN circuit</div>
      </div>
      <Handle
        type="source"
        id="internet"
        position={Position.Bottom}
        style={{ ...HANDLE_STYLE, inset: "auto 0 -4px 0", height: 8 }}
      />
    </div>
  );
}
