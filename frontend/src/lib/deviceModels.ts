/**
 * Device model lookup.
 *
 * Phase 2 MVP: the server's DeviceTemplate rows carry canonical metadata
 * (model_display, device_family), but several UI surfaces (port map,
 * radio panel) need extra layout hints the template doesn't store yet —
 * e.g. physical port count, port grouping, radio band split.
 *
 * Until the DeviceTemplate admin grows those fields, this client-side
 * table keeps the UI useful. Unknown models degrade to a safe default.
 */

export type PortKind = "ethernet" | "sfp" | "sfp+" | "console";

export type ModelProfile = {
  family: "ap" | "switch" | "gateway" | "other";
  ports?: { count: number; kind: PortKind; poe?: boolean }[];
  radios?: { band: "2.4GHz" | "5GHz" | "6GHz"; name: string }[];
};

const PROFILES: Record<string, ModelProfile> = {
  USW24P250: {
    family: "switch",
    ports: [
      { count: 24, kind: "ethernet", poe: true },
      { count: 2, kind: "sfp" },
    ],
  },
  "U6-Pro": {
    family: "ap",
    radios: [
      { band: "2.4GHz", name: "Radio 0" },
      { band: "5GHz", name: "Radio 1" },
    ],
  },
  UDR: {
    family: "gateway",
    ports: [{ count: 4, kind: "ethernet", poe: false }],
    radios: [
      { band: "2.4GHz", name: "Radio 0" },
      { band: "5GHz", name: "Radio 1" },
    ],
  },
};

export function profileFor(modelCode: string): ModelProfile {
  return PROFILES[modelCode] ?? { family: "other" };
}

export function portCount(modelCode: string): number {
  const profile = profileFor(modelCode);
  return (profile.ports ?? []).reduce((sum, p) => sum + p.count, 0);
}
