/** Patch a cable: pick two free ports and a cable grade. */

import { useEffect, useMemo, useState } from "react";

import { post, useCatalog, useDevices, useLinks, useSiteMutation } from "@/api/client";
import { Button, Field, Modal, Select, useToast } from "@/components/ui";
import { speed } from "@/lib/format";
import type { LinkRow, PortRow } from "@/types";

interface Endpoint {
  deviceId: number | null;
  portId: number | null;
}

export function LinkDialog({
  open,
  onClose,
  siteId,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  siteId: number | null;
  initial?: { aPortId?: number; bDeviceId?: number };
}) {
  const toast = useToast();
  const devices = useDevices(siteId);
  const links = useLinks(siteId);
  const catalog = useCatalog();

  const patched = useMemo(() => {
    const used = new Set<number>();
    for (const link of links.data ?? []) {
      used.add(link.a_port);
      used.add(link.b_port);
    }
    return used;
  }, [links.data]);

  const freePorts = (deviceId: number | null): PortRow[] => {
    const device = devices.data?.find((item) => item.id === deviceId);
    return (device?.ports ?? []).filter((port) => !patched.has(port.id));
  };

  const [a, setA] = useState<Endpoint>({ deviceId: null, portId: null });
  const [b, setB] = useState<Endpoint>({ deviceId: null, portId: null });
  const [cable, setCable] = useState("cat6");

  useEffect(() => {
    if (!open || !devices.data?.length) return;
    const aPort = initial?.aPortId
      ? devices.data.flatMap((d) => d.ports).find((p) => p.id === initial.aPortId)
      : undefined;
    setA({
      deviceId: aPort?.device ?? devices.data[0].id,
      portId: aPort?.id ?? null,
    });
    setB({ deviceId: initial?.bDeviceId ?? devices.data[1]?.id ?? null, portId: null });
  }, [open, devices.data, initial?.aPortId, initial?.bDeviceId]);

  const aPort = freePorts(a.deviceId).find((port) => port.id === a.portId);
  const bPort = freePorts(b.deviceId).find((port) => port.id === b.portId);

  // Only offer the other end ports that could physically take the same cable.
  const compatible = (port: PortRow) =>
    !aPort || mediaFamily(port.media) === mediaFamily(aPort.media);

  useEffect(() => {
    if (!aPort) return;
    setCable(mediaFamily(aPort.media) === "fibre" ? "dac" : "cat6");
  }, [aPort?.id, aPort?.media, aPort]);

  const create = useSiteMutation(siteId, () =>
    post<LinkRow>("/links/", {
      site: siteId,
      a_port: a.portId,
      b_port: b.portId,
      cable,
    }),
  );

  const cableOptions = Object.keys(catalog.data?.cables ?? { cat6: 0 }).filter((name) =>
    aPort ? cableFamily(name) === mediaFamily(aPort.media) : true,
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Patch a cable"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!a.portId || !b.portId || create.isPending}
            onClick={() =>
              create
                .mutateAsync()
                .then(() => {
                  toast("Cable patched.");
                  onClose();
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Patch
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <EndpointPicker
          label="From"
          endpoint={a}
          onChange={setA}
          devices={devices.data ?? []}
          ports={freePorts(a.deviceId)}
        />
        <EndpointPicker
          label="To"
          endpoint={b}
          onChange={setB}
          devices={(devices.data ?? []).filter((device) => device.id !== a.deviceId)}
          ports={freePorts(b.deviceId).filter(compatible)}
        />
        <Field
          label="Cable"
          hint={
            aPort && bPort
              ? `Negotiates at ${speed(
                  Math.min(
                    aPort.max_speed_mbps,
                    bPort.max_speed_mbps,
                    catalog.data?.cables[cable] ?? 25000,
                  ),
                )}`
              : undefined
          }
        >
          <Select value={cable} onChange={(event) => setCable(event.target.value)}>
            {cableOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function EndpointPicker({
  label,
  endpoint,
  onChange,
  devices,
  ports,
}: {
  label: string;
  endpoint: Endpoint;
  onChange: (value: Endpoint) => void;
  devices: { id: number; name: string; model_name: string }[];
  ports: PortRow[];
}) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <Field label={`${label} device`}>
        <Select
          value={endpoint.deviceId ?? ""}
          onChange={(event) =>
            onChange({ deviceId: Number(event.target.value), portId: null })
          }
        >
          <option value="">Select…</option>
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Port" hint={ports.length ? undefined : "No free ports on this device"}>
        <Select
          value={endpoint.portId ?? ""}
          onChange={(event) =>
            onChange({ ...endpoint, portId: Number(event.target.value) })
          }
        >
          <option value="">Select…</option>
          {ports.map((port) => (
            <option key={port.id} value={port.id}>
              {port.label} · {port.media.toUpperCase()} {speed(port.max_speed_mbps)}
              {port.poe_out ? " · PoE" : ""}
            </option>
          ))}
        </Select>
      </Field>
    </div>
  );
}

function mediaFamily(media: string): string {
  return media === "rj45" ? "copper" : "fibre";
}

function cableFamily(cable: string): string {
  return cable === "dac" || cable === "fibre" ? "fibre" : "copper";
}
