/** The port panel, laid out the way the ports sit on the physical hardware. */

import { BoltIcon } from "@/components/icons";
import { cx } from "@/components/ui";
import { speed } from "@/lib/format";
import type { SimDevice, SimPort } from "@/types";

export function portTone(port: SimPort): {
  className: string;
  label: string;
} {
  if (!port.enabled) return { className: "bg-ink-850 text-ink-600 border-ink-700", label: "Disabled" };
  if (port.stp_state === "err-disabled")
    return { className: "bg-bad/25 text-bad border-bad/50", label: "Err-disabled" };
  if (!port.link_id && port.client_ids.length === 0)
    return { className: "bg-ink-850 text-ink-500 border-ink-700", label: "Not connected" };
  if (port.stp_state === "discarding")
    return { className: "bg-warn/25 text-warn border-warn/50", label: "Blocking" };
  if (port.utilisation >= 0.9)
    return { className: "bg-bad/25 text-bad border-bad/50", label: "Saturated" };
  return { className: "bg-ok/20 text-ok border-ok/40", label: "Connected" };
}

export function PortGrid({
  device,
  selectedPortId,
  onSelect,
}: {
  device: SimDevice;
  selectedPortId?: string | null;
  onSelect?: (port: SimPort) => void;
}) {
  const copper = device.ports.filter((port) => port.media === "rj45");
  const fibre = device.ports.filter((port) => port.media !== "rj45");
  const twoRow = copper.length > 6;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-4 rounded-lg border border-ink-800 bg-ink-950/60 p-3">
        {copper.length > 0 && (
          <div
            className={cx("grid gap-1", twoRow ? "grid-flow-col grid-rows-2" : "grid-flow-col")}
          >
            {copper.map((port) => (
              <PortChip
                key={port.id}
                port={port}
                selected={port.id === selectedPortId}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
        {fibre.length > 0 && (
          <div className="flex flex-col gap-1 border-l border-ink-800 pl-4">
            <div className={cx("grid gap-1", fibre.length > 4 ? "grid-flow-col grid-rows-2" : "grid-flow-col")}>
              {fibre.map((port) => (
                <PortChip
                  key={port.id}
                  port={port}
                  selected={port.id === selectedPortId}
                  onSelect={onSelect}
                  fibre
                />
              ))}
            </div>
            <span className="text-[10px] uppercase tracking-wider text-ink-500">SFP</span>
          </div>
        )}
      </div>
      <Legend />
    </div>
  );
}

function PortChip({
  port,
  selected,
  onSelect,
  fibre,
}: {
  port: SimPort;
  selected?: boolean;
  onSelect?: (port: SimPort) => void;
  fibre?: boolean;
}) {
  const tone = portTone(port);
  const powering = port.poe_delivered_w > 0;
  return (
    <button
      type="button"
      onClick={() => onSelect?.(port)}
      title={`${port.label} · ${tone.label}${port.speed_mbps ? ` · ${speed(port.speed_mbps)}` : ""}`}
      className={cx(
        "relative grid h-8 w-8 place-items-center rounded border text-[10px] font-semibold transition",
        fibre && "rounded-sm",
        tone.className,
        selected && "ring-2 ring-unifi-bright ring-offset-1 ring-offset-ink-950",
        onSelect && "hover:brightness-125",
      )}
    >
      {port.role === "wan" ? "W" : port.index}
      {powering && (
        <BoltIcon size={9} className="absolute -right-0.5 -top-0.5 text-warn" strokeWidth={3} />
      )}
    </button>
  );
}

function Legend() {
  const items = [
    { label: "Connected", className: "bg-ok/20 border-ok/40" },
    { label: "Blocked by STP", className: "bg-warn/25 border-warn/50" },
    { label: "Err-disabled", className: "bg-bad/25 border-bad/50" },
    { label: "Free", className: "bg-ink-850 border-ink-700" },
  ];
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-500">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className={cx("inline-block h-3 w-3 rounded-sm border", item.className)} />
          {item.label}
        </span>
      ))}
      <span className="flex items-center gap-1">
        <BoltIcon size={11} className="text-warn" /> Supplying PoE
      </span>
    </div>
  );
}
