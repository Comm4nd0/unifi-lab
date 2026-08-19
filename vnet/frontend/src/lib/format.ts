/** Formatting helpers shared across the console. */

export function mbps(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} Gbps`;
  if (value >= 10) return `${value.toFixed(0)} Mbps`;
  if (value > 0 && value < 0.1) return "<0.1 Mbps";
  return `${value.toFixed(1)} Mbps`;
}

export function speed(value: number): string {
  if (!value) return "—";
  return value >= 1000 ? `${value / 1000}G` : `${value}M`;
}

export function watts(value: number): string {
  return `${value.toFixed(value < 10 ? 1 : 0)} W`;
}

export function percent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** Green below 70%, amber to 90%, red above. Matches the console's link colours. */
export function loadTone(utilisation: number): "ok" | "warn" | "bad" {
  if (utilisation >= 0.9) return "bad";
  if (utilisation >= 0.7) return "warn";
  return "ok";
}

export const TONE_TEXT = { ok: "text-ok", warn: "text-warn", bad: "text-bad" } as const;
export const TONE_BG = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" } as const;

export function relativeSpeedLabel(port: { speed_mbps: number; max_speed_mbps: number }): string {
  if (!port.speed_mbps) return "Down";
  return port.speed_mbps < port.max_speed_mbps
    ? `${speed(port.speed_mbps)} (of ${speed(port.max_speed_mbps)})`
    : speed(port.speed_mbps);
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/[-_]/g, " ");
}

/** Human labels for issue categories — "stp" should never render as "Stp". */
const CATEGORY_LABELS: Record<string, string> = {
  stp: "STP",
  power: "Power",
  capacity: "Capacity",
  topology: "Topology",
  config: "Config",
  general: "General",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? titleCase(category);
}
