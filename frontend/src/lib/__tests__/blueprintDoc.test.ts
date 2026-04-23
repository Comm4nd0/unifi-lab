import { describe, expect, test } from "vitest";

import {
  addDevice,
  nextHostname,
  parseBlueprintYaml,
  removeDevice,
  renameDevice,
  setUplink,
  stringifyBlueprint,
  type BlueprintDoc,
} from "../blueprintDoc";

const SAMPLE = `schema_version: uvl-blueprint/v1
name: example-home
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
  devices:
    - hostname: gateway
      model: UDR
    - hostname: switch-main
      model: USW24P250
      uplink: gateway
    - hostname: ap-office
      model: U6-Pro
      uplink: switch-main
`;

describe("parseBlueprintYaml", () => {
  test("extracts devices and preserves everything else in rest", () => {
    const doc = parseBlueprintYaml(SAMPLE);
    expect(doc).not.toBeNull();
    expect(doc!.devices.map((d) => d.hostname)).toEqual([
      "gateway",
      "switch-main",
      "ap-office",
    ]);
    // The switch's uplink round-trips as a string.
    const sw = doc!.devices.find((d) => d.hostname === "switch-main");
    expect(sw?.uplink).toBe("gateway");
    // Non-device site keys are kept pristine in rest.
    expect(doc!.rest).toMatchObject({
      schema_version: "uvl-blueprint/v1",
      name: "example-home",
    });
    const restSite = doc!.rest.site as { networks?: unknown; devices?: unknown };
    expect(Array.isArray(restSite.networks)).toBe(true);
    // devices key is pulled out of rest so it can't drift.
    expect(restSite.devices).toBeUndefined();
  });

  test("normalises missing uplink to null", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const gw = doc.devices.find((d) => d.hostname === "gateway");
    expect(gw?.uplink).toBeNull();
  });

  test("returns null on malformed YAML", () => {
    expect(parseBlueprintYaml("name: [unterminated")).toBeNull();
  });

  test("returns empty-but-valid doc on empty source", () => {
    const doc = parseBlueprintYaml("");
    expect(doc).toEqual({ devices: [], rest: {} });
  });
});

describe("stringifyBlueprint", () => {
  test("round-trips without losing non-device keys", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const yaml = stringifyBlueprint(doc);
    // Must still contain the network block we pulled from rest.
    expect(yaml).toContain("networks:");
    expect(yaml).toContain("vlan: 1");
    // And all three devices with their uplinks.
    expect(yaml).toContain("hostname: gateway");
    expect(yaml).toContain("uplink: gateway");
    expect(yaml).toContain("uplink: switch-main");
  });

  test("omits uplink key when null", () => {
    const doc: BlueprintDoc = {
      devices: [{ hostname: "gw", model: "UDR", uplink: null }],
      rest: {},
    };
    expect(stringifyBlueprint(doc)).not.toContain("uplink:");
  });

  test("stringify then parse is a fixed point for the devices list", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const reparsed = parseBlueprintYaml(stringifyBlueprint(doc))!;
    expect(reparsed.devices).toEqual(doc.devices);
  });
});

describe("nextHostname", () => {
  test("starts at -1 when the family is unused", () => {
    expect(nextHostname("switch", [])).toBe("switch-1");
  });

  test("increments past the highest existing index, not the count", () => {
    const existing = [
      { hostname: "switch-1", model: "x" },
      { hostname: "switch-5", model: "x" },
    ];
    expect(nextHostname("switch", existing)).toBe("switch-6");
  });

  test("ignores other families and free-form hostnames", () => {
    const existing = [
      { hostname: "ap-2", model: "x" },
      { hostname: "my-switch", model: "x" },
      { hostname: "switch-3", model: "x" },
    ];
    expect(nextHostname("switch", existing)).toBe("switch-4");
  });

  test("falls back to 'device' when family is empty", () => {
    expect(nextHostname("", [])).toBe("device-1");
  });
});

describe("addDevice", () => {
  test("appends without mutating the input doc", () => {
    const doc: BlueprintDoc = { devices: [], rest: {} };
    const next = addDevice(doc, { hostname: "gw", model: "UDR" });
    expect(doc.devices).toHaveLength(0);
    expect(next.devices).toHaveLength(1);
  });
});

describe("removeDevice", () => {
  test("drops the named device", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const next = removeDevice(doc, "switch-main");
    expect(next.devices.map((d) => d.hostname)).toEqual(["gateway", "ap-office"]);
  });

  test("scrubs children's uplink when parent is removed", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const next = removeDevice(doc, "switch-main");
    const orphan = next.devices.find((d) => d.hostname === "ap-office");
    expect(orphan?.uplink).toBeNull();
  });
});

describe("renameDevice", () => {
  test("renames the device and fixes children's uplinks", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const next = renameDevice(doc, "switch-main", "core-switch")!;
    expect(next.devices.some((d) => d.hostname === "switch-main")).toBe(false);
    expect(next.devices.some((d) => d.hostname === "core-switch")).toBe(true);
    const ap = next.devices.find((d) => d.hostname === "ap-office");
    expect(ap?.uplink).toBe("core-switch");
  });

  test("returns null when the new hostname clashes with another device", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    expect(renameDevice(doc, "switch-main", "gateway")).toBeNull();
  });

  test("same-name rename is a no-op", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    expect(renameDevice(doc, "gateway", "gateway")).toBe(doc);
  });

  test("refuses an empty new hostname", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    expect(renameDevice(doc, "gateway", "")).toBe(doc);
  });
});

describe("setUplink", () => {
  test("sets an uplink when target and parent both exist", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const next = setUplink(doc, "gateway", "switch-main");
    const gw = next.devices.find((d) => d.hostname === "gateway");
    expect(gw?.uplink).toBe("switch-main");
  });

  test("clears uplink when passed null", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    const next = setUplink(doc, "switch-main", null);
    const sw = next.devices.find((d) => d.hostname === "switch-main");
    expect(sw?.uplink).toBeNull();
  });

  test("refuses to uplink to self", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    expect(setUplink(doc, "gateway", "gateway")).toBe(doc);
  });

  test("refuses to uplink to a non-existent device", () => {
    const doc = parseBlueprintYaml(SAMPLE)!;
    expect(setUplink(doc, "gateway", "nowhere")).toBe(doc);
  });
});
