/**
 * Blueprint document helpers — the bridge between visual-canvas edits
 * and the YAML source the backend validator consumes.
 *
 * Kept as pure functions so the canvas component can stay thin and so
 * these can be unit-tested without mounting React.
 */

import { parse as yamlParse, stringify as yamlStringify } from "yaml";

export type BlueprintDevice = {
  hostname: string;
  model: string;
  uplink?: string | null;
  // Arbitrary passthrough fields (mac, role, network, …) preserved during
  // visual edits. We never write them from the canvas, but we never drop
  // them either.
  [extra: string]: unknown;
};

type UnknownRecord = Record<string, unknown>;

/**
 * Top-level blueprint shape we care about. Anything we don't recognise is
 * preserved in the passthrough layer — ``schema_version``, ``name``,
 * ``description``, and non-``devices`` keys inside ``site`` (``networks``,
 * ``wlans``, ``clients``, …) are written back untouched.
 */
export type BlueprintDoc = {
  devices: BlueprintDevice[];
  /** The original parsed object, minus a pulled-out ``devices`` list. */
  rest: UnknownRecord;
};

export const EMPTY_DOC: BlueprintDoc = { devices: [], rest: {} };

function isObject(v: unknown): v is UnknownRecord {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Parse a YAML blueprint source into a structured doc.
 *
 * Returns ``null`` when the YAML is malformed — callers treat that as
 * "leave the existing doc alone, surface the validation error".
 */
export function parseBlueprintYaml(source: string): BlueprintDoc | null {
  let parsed: unknown;
  try {
    parsed = yamlParse(source);
  } catch {
    return null;
  }
  if (!isObject(parsed)) return { devices: [], rest: {} };

  const rest: UnknownRecord = { ...parsed };
  let devices: BlueprintDevice[] = [];

  const site = parsed.site;
  if (isObject(site)) {
    const siteCopy: UnknownRecord = { ...site };
    const raw = Array.isArray(site.devices) ? site.devices : [];
    devices = raw
      .filter(isObject)
      .map((d) => ({
        ...d,
        hostname: typeof d.hostname === "string" ? d.hostname : "",
        model: typeof d.model === "string" ? d.model : "",
        uplink:
          typeof d.uplink === "string" && d.uplink.length > 0 ? d.uplink : null,
      }));
    delete siteCopy.devices;
    rest.site = siteCopy;
  }

  return { devices, rest };
}

/** Stringify a doc back to YAML, merging devices into ``site.devices``. */
export function stringifyBlueprint(doc: BlueprintDoc): string {
  const restSite = isObject(doc.rest.site) ? doc.rest.site : {};
  const merged: UnknownRecord = {
    ...doc.rest,
    site: {
      ...restSite,
      devices: doc.devices.map((d) => {
        const out: UnknownRecord = { ...d };
        // Drop null uplinks — they round-trip as "no uplink declared".
        if (out.uplink == null) delete out.uplink;
        return out;
      }),
    },
  };
  // When the YAML is brand-new (no schema_version authored yet) this
  // still emits something parseable. The validator will warn, not
  // reject, on a missing schema_version.
  return yamlStringify(merged);
}

/** Next hostname for a family: ``switch-1``, ``switch-2``, … */
export function nextHostname(family: string, existing: BlueprintDevice[]): string {
  const prefix = (family || "device").toLowerCase();
  const re = new RegExp(`^${prefix}-(\\d+)$`);
  let highest = 0;
  for (const d of existing) {
    const match = d.hostname?.match(re);
    if (match) {
      const n = Number(match[1]);
      if (Number.isFinite(n) && n > highest) highest = n;
    }
  }
  return `${prefix}-${highest + 1}`;
}

/** Append a device; caller supplies hostname+model. Returns a new doc. */
export function addDevice(doc: BlueprintDoc, device: BlueprintDevice): BlueprintDoc {
  return { ...doc, devices: [...doc.devices, device] };
}

/** Remove a device by hostname and scrub any children's uplinks that pointed at it. */
export function removeDevice(doc: BlueprintDoc, hostname: string): BlueprintDoc {
  const next: BlueprintDevice[] = [];
  for (const d of doc.devices) {
    if (d.hostname === hostname) continue;
    if (d.uplink === hostname) {
      next.push({ ...d, uplink: null });
    } else {
      next.push(d);
    }
  }
  return { ...doc, devices: next };
}

/**
 * Rename a device. Returns the new doc, or ``null`` if the new hostname
 * already exists on a different device (uniqueness is a hard rule on the
 * backend validator — we mirror it here to avoid a round-trip failure).
 */
export function renameDevice(
  doc: BlueprintDoc,
  oldHostname: string,
  newHostname: string,
): BlueprintDoc | null {
  if (!newHostname || newHostname === oldHostname) return doc;
  if (doc.devices.some((d) => d.hostname === newHostname)) return null;
  const next: BlueprintDevice[] = doc.devices.map((d) => {
    if (d.hostname === oldHostname) return { ...d, hostname: newHostname };
    if (d.uplink === oldHostname) return { ...d, uplink: newHostname };
    return d;
  });
  return { ...doc, devices: next };
}

/** Set (or clear, via ``null``) the uplink of a target device. */
export function setUplink(
  doc: BlueprintDoc,
  target: string,
  uplink: string | null,
): BlueprintDoc {
  // Cannot uplink to self, and the uplinked device must actually exist.
  if (uplink === target) return doc;
  if (uplink !== null && !doc.devices.some((d) => d.hostname === uplink)) {
    return doc;
  }
  const next = doc.devices.map((d) =>
    d.hostname === target ? { ...d, uplink: uplink ?? null } : d,
  );
  return { ...doc, devices: next };
}
