/** Helpers that read the simulation payload the same way on every page. */

import type { SimDevice, Simulation } from "@/types";

/** What sits above this device: the internet circuit, another box, or nothing. */
export function uplinkLabel(sim: Simulation, device: SimDevice): string {
  if (device.uplink_kind === "internet") return "Internet";
  const upstream = sim.devices.find((item) => item.id === device.uplink_device_id);
  return upstream?.name ?? "—";
}
