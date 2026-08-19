/** Everything about one device: state, its ports, and its configuration. */

import { useMemo, useState } from "react";

import { del, patch, useDevices, useSiteMutation } from "@/api/client";
import { PortGrid, portTone } from "@/components/PortGrid";
import { CloseIcon, LINE_ICONS, TrashIcon } from "@/components/icons";
import {
  Badge,
  Button,
  Field,
  Input,
  Meter,
  Select,
  StatusDot,
  Toggle,
  cx,
  useToast,
} from "@/components/ui";
import { loadTone, mbps, percent, speed, titleCase, watts } from "@/lib/format";
import { uplinkLabel } from "@/lib/topology";
import { useUi } from "@/store";
import type { SimDevice, SimPort, Simulation } from "@/types";

/** Map simulation port ids ("<device>:<index>") onto database port ids. */
export function usePortIdMap(siteId: number | null): Map<string, number> {
  const devices = useDevices(siteId);
  return useMemo(() => {
    const map = new Map<string, number>();
    for (const device of devices.data ?? []) {
      for (const port of device.ports) map.set(`${device.id}:${port.index}`, port.id);
    }
    return map;
  }, [devices.data]);
}

type Tab = "overview" | "ports" | "config";

export function DeviceDetail({
  device,
  simulation,
  onClose,
}: {
  device: SimDevice;
  simulation: Simulation;
  onClose?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const Icon = LINE_ICONS[device.line] ?? LINE_ICONS.other;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-start gap-3 border-b border-ink-800 px-4 py-3">
        <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-md bg-ink-800 text-unifi-bright">
          <Icon size={19} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StatusDot status={device.status} />
            <h2 className="truncate text-sm font-semibold text-ink-100">{device.name}</h2>
          </div>
          <p className="mt-0.5 truncate text-xs text-ink-400">
            {device.model_name} · {device.ip || "no IP"} · {device.mac}
          </p>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-ink-500 hover:text-ink-200">
            <CloseIcon size={16} />
          </button>
        )}
      </header>

      <nav className="flex gap-1 border-b border-ink-800 px-3">
        {(["overview", "ports", "config"] as Tab[]).map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-xs font-medium capitalize transition",
              tab === item
                ? "border-unifi-bright text-unifi-bright"
                : "border-transparent text-ink-400 hover:text-ink-200",
            )}
          >
            {item === "config" ? "Configuration" : item}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === "overview" && <Overview device={device} simulation={simulation} />}
        {tab === "ports" && <Ports device={device} simulation={simulation} />}
        {tab === "config" && <Config device={device} onDeleted={onClose} />}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- overview */

function Overview({ device, simulation }: { device: SimDevice; simulation: Simulation }) {
  const uplink = uplinkLabel(simulation, device);
  const bridge = device.stp;
  const root = bridge ? simulation.devices.find((d) => d.id === bridge.root_device_id) : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Throughput" value={mbps(device.throughput_mbps)} />
        <Metric label="Clients" value={String(device.client_count)} />
        <Metric label="Uplink" value={uplink} />
        <Metric
          label="Status"
          value={titleCase(device.status)}
          tone={device.status === "online" ? "ok" : device.status === "offline" ? "warn" : "bad"}
        />
      </div>

      {device.poe_budget_w > 0 && (
        <Section title="PoE budget">
          <div className="flex items-center justify-between text-xs text-ink-400">
            <span>
              {watts(device.poe_used_w)} of {watts(device.poe_budget_w)}
            </span>
            <span>{percent(device.poe_used_w / device.poe_budget_w)}</span>
          </div>
          <Meter
            className="mt-2"
            value={device.poe_used_w / device.poe_budget_w}
            tone={loadTone(device.poe_used_w / device.poe_budget_w)}
          />
        </Section>
      )}

      {device.wireless && (
        <Section title="Radio">
          <div className="flex items-center justify-between text-xs text-ink-400">
            <span>
              {device.wireless.client_count} clients · {mbps(device.wireless.demand_mbps)} of{" "}
              {mbps(device.wireless.capacity_mbps)} usable
            </span>
            <span>{percent(device.wireless.utilisation)}</span>
          </div>
          <Meter
            className="mt-2"
            value={device.wireless.utilisation}
            tone={loadTone(device.wireless.utilisation)}
          />
        </Section>
      )}

      <Section title="Spanning tree">
        {bridge ? (
          <dl className="grid grid-cols-2 gap-y-2 text-xs">
            <Detail term="Bridge ID" value={bridge.bridge_id} mono />
            <Detail
              term="Role"
              value={bridge.is_root ? "Root bridge" : `Path to ${root?.name ?? "root"}`}
            />
            <Detail term="Root path cost" value={String(bridge.root_path_cost)} />
            <Detail
              term="Root port"
              value={
                bridge.root_port_id
                  ? (device.ports.find((p) => p.id === bridge.root_port_id)?.label ?? "—")
                  : "—"
              }
            />
          </dl>
        ) : (
          <p className="text-xs text-ink-400">
            {device.stp_enabled
              ? "This model does not run spanning tree. It forwards frames straight through, so a loop through it cannot be broken automatically."
              : "Spanning tree is switched off on this device."}
          </p>
        )}
      </Section>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad";
}) {
  const toneClass = tone ? { ok: "text-ok", warn: "text-warn", bad: "text-bad" }[tone] : "text-ink-100";
  return (
    <div className="rounded-md border border-ink-800 bg-ink-850/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
      <div className={cx("mt-0.5 truncate text-sm font-medium tabular-nums", toneClass)}>
        {value}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Detail({ term, value, mono }: { term: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-ink-500">{term}</dt>
      <dd className={cx("text-ink-200", mono && "font-mono text-[11px]")}>{value}</dd>
    </div>
  );
}

/* ------------------------------------------------------------------ ports */

function Ports({ device, simulation }: { device: SimDevice; simulation: Simulation }) {
  const [selectedId, setSelectedId] = useState<string | null>(device.ports[0]?.id ?? null);
  const selected = device.ports.find((port) => port.id === selectedId) ?? null;

  return (
    <div className="space-y-4">
      <PortGrid device={device} selectedPortId={selectedId} onSelect={(p) => setSelectedId(p.id)} />
      {selected && <PortInspector port={selected} simulation={simulation} />}
    </div>
  );
}

function PortInspector({ port, simulation }: { port: SimPort; simulation: Simulation }) {
  const toast = useToast();
  const { siteId } = useUi();
  const portIds = usePortIdMap(siteId);
  const rowId = portIds.get(port.id);
  const peerDevice = port.peer_device_id
    ? simulation.devices.find((d) => d.id === port.peer_device_id)
    : null;
  const peerPort = peerDevice?.ports.find((p) => p.id === port.peer_port_id);
  const tone = portTone(port);

  const update = useSiteMutation(siteId, (body: Record<string, unknown>) =>
    patch(`/ports/${rowId}/`, body),
  );
  const unplug = useSiteMutation(siteId, (linkId: string) => del(`/links/${linkId}/`));

  return (
    <div className="rounded-md border border-ink-800 bg-ink-850/50 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-ink-100">{port.label}</h3>
        <Badge
          tone={
            tone.label === "Connected"
              ? "ok"
              : tone.label === "Blocking"
                ? "warn"
                : tone.label === "Err-disabled" || tone.label === "Saturated"
                  ? "bad"
                  : "neutral"
          }
        >
          {tone.label}
        </Badge>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-y-2 text-xs">
        <Detail term="Media" value={`${port.media.toUpperCase()} · ${speed(port.max_speed_mbps)}`} />
        <Detail term="Negotiated" value={port.speed_mbps ? speed(port.speed_mbps) : "—"} />
        <Detail
          term="Connected to"
          value={peerDevice ? `${peerDevice.name} · ${peerPort?.label ?? ""}` : "Nothing"}
        />
        <Detail term="STP role" value={port.stp_role ? titleCase(port.stp_role) : "—"} />
        <Detail term="Load" value={mbps(port.load_mbps)} />
        <Detail term="PoE" value={port.poe_out ? `${port.poe_out} · ${watts(port.poe_max_w)}` : "—"} />
      </dl>

      {port.stp_reason && (
        <p className="mt-2 rounded border border-warn/30 bg-warn/10 px-2 py-1.5 text-[11px] text-warn">
          {port.stp_reason}
        </p>
      )}

      {port.utilisation > 0 && (
        <Meter className="mt-3" value={port.utilisation} tone={loadTone(port.utilisation)} />
      )}

      {rowId !== undefined && (
        <div className="mt-3 space-y-1 border-t border-ink-800 pt-3">
          <Toggle
            label="Port enabled"
            checked={port.enabled}
            onChange={(value) => update.mutate({ enabled: value })}
          />
          {port.poe_out && (
            <Toggle
              label="PoE output"
              hint={`Supplies ${port.poe_out} up to ${watts(port.poe_max_w)}`}
              checked={port.poe_enabled}
              onChange={(value) => update.mutate({ poe_enabled: value })}
            />
          )}
          <Toggle
            label="BPDU guard"
            hint="Shut the port down if another switch appears on it"
            checked={port.bpdu_guard}
            onChange={(value) => update.mutate({ bpdu_guard: value })}
          />
          {port.link_id && (
            <Button
              variant="danger"
              size="sm"
              className="mt-2 w-full"
              onClick={() =>
                unplug
                  .mutateAsync(port.link_id!)
                  .then(() => toast("Cable removed."))
                  .catch((error: Error) => toast(error.message, "bad"))
              }
            >
              Unplug cable
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- config */

const PRIORITIES = [0, 4096, 8192, 16384, 24576, 32768, 40960, 49152];

function Config({ device, onDeleted }: { device: SimDevice; onDeleted?: () => void }) {
  const toast = useToast();
  const { siteId, selectDevice } = useUi();
  const [name, setName] = useState(device.name);

  const update = useSiteMutation(siteId, (body: Record<string, unknown>) =>
    patch(`/devices/${device.id}/`, body),
  );
  const remove = useSiteMutation(siteId, () => del(`/devices/${device.id}/`));

  return (
    <div className="space-y-4">
      <Field label="Name">
        <div className="flex gap-2">
          <Input value={name} onChange={(event) => setName(event.target.value)} />
          <Button
            disabled={name === device.name || !name.trim()}
            onClick={() => update.mutate({ name: name.trim() })}
          >
            Save
          </Button>
        </div>
      </Field>

      <div className="border-t border-ink-800 pt-3">
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
          Spanning tree
        </h3>
        <Toggle
          label="Run spanning tree"
          hint="Turning this off makes the device forward blindly, like an unmanaged switch"
          checked={device.stp_enabled}
          disabled={!device.stp}
          onChange={(value) => update.mutate({ stp_enabled: value })}
        />
        <Field label="Bridge priority" className="mt-2" hint="Lower wins the root election">
          <Select
            value={device.stp_priority}
            onChange={(event) => update.mutate({ stp_priority: Number(event.target.value) })}
          >
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {value}
                {value === 32768 ? " (default)" : ""}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="border-t border-ink-800 pt-3">
        <Button
          variant="danger"
          className="w-full"
          onClick={() =>
            remove
              .mutateAsync()
              .then(() => {
                toast(`${device.name} removed.`);
                selectDevice(null);
                onDeleted?.();
              })
              .catch((error: Error) => toast(error.message, "bad"))
          }
        >
          <TrashIcon size={14} /> Remove {device.name}
        </Button>
      </div>
    </div>
  );
}
