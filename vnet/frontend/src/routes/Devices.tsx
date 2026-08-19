import { useState } from "react";

import { useSimulation } from "@/api/client";
import { AddDeviceDialog } from "@/components/AddDeviceDialog";
import { DeviceDetail } from "@/components/DeviceDetail";
import { LinkDialog } from "@/components/LinkDialog";
import { LINE_ICONS, PlusIcon } from "@/components/icons";
import { Badge, Button, EmptyState, Meter, Panel, StatusDot, Table, Tr } from "@/components/ui";
import { loadTone, mbps, percent, watts } from "@/lib/format";
import { uplinkLabel } from "@/lib/topology";
import { useUi } from "@/store";

export function DevicesPage() {
  const { siteId, selectedDeviceId, selectDevice } = useUi();
  const { data: sim } = useSimulation(siteId);
  const [adding, setAdding] = useState(false);
  const [patching, setPatching] = useState(false);

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading devices…</div>;

  const selected = sim.devices.find((device) => device.id === selectedDeviceId) ?? null;

  return (
    <div className="flex h-full min-h-0">
      <div className="min-w-0 flex-1 overflow-auto p-5">
        <Panel
          title="Devices"
          subtitle={`${sim.devices.length} in this site`}
          bodyClassName="p-0"
          action={
            <div className="flex gap-2">
              <Button size="sm" onClick={() => setPatching(true)}>
                Patch cable
              </Button>
              <Button size="sm" variant="primary" onClick={() => setAdding(true)}>
                <PlusIcon size={14} /> Add device
              </Button>
            </div>
          }
        >
          {sim.devices.length === 0 ? (
            <EmptyState
              title="No devices yet"
              detail="Pick something from the UniFi catalogue to get started."
              action={
                <Button variant="primary" onClick={() => setAdding(true)}>
                  Add your first device
                </Button>
              }
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Model</th>
                  <th className="th">IP</th>
                  <th className="th">Uplink</th>
                  <th className="th text-right">Ports</th>
                  <th className="th text-right">PoE</th>
                  <th className="th w-40">Throughput</th>
                </tr>
              </thead>
              <tbody>
                {sim.devices.map((device) => {
                  const Icon = LINE_ICONS[device.line] ?? LINE_ICONS.other;
                  const used = device.ports.filter((port) => port.link_id).length;
                  const uplink = uplinkLabel(sim, device);
                  const capacity = Math.max(
                    ...device.ports.map((port) => port.max_speed_mbps),
                    1,
                  );
                  return (
                    <Tr
                      key={device.id}
                      active={device.id === selectedDeviceId}
                      onClick={() => selectDevice(device.id)}
                    >
                      <td className="td">
                        <div className="flex items-center gap-2">
                          <Icon size={15} className="text-ink-400" />
                          <StatusDot status={device.status} />
                          <span className="font-medium text-ink-100">{device.name}</span>
                          {device.stp?.is_root && <Badge tone="info">root bridge</Badge>}
                          {!device.stp_enabled && <Badge tone="warn">STP off</Badge>}
                        </div>
                      </td>
                      <td className="td text-ink-400">{device.model_name}</td>
                      <td className="td font-mono text-xs text-ink-400">{device.ip || "—"}</td>
                      <td className="td text-ink-400">{uplink}</td>
                      <td className="td text-right tabular-nums text-ink-400">
                        {used}/{device.ports.length}
                      </td>
                      <td className="td text-right tabular-nums text-ink-400">
                        {device.poe_budget_w
                          ? `${watts(device.poe_used_w)} / ${watts(device.poe_budget_w)}`
                          : device.power_draw_w
                            ? `${watts(device.power_draw_w)} draw`
                            : "—"}
                      </td>
                      <td className="td">
                        <div className="mb-1 text-xs tabular-nums text-ink-300">
                          {mbps(device.throughput_mbps)}
                          <span className="ml-1 text-ink-500">
                            {percent(Math.min(device.throughput_mbps / capacity, 1))}
                          </span>
                        </div>
                        <Meter
                          value={device.throughput_mbps / capacity}
                          tone={loadTone(device.throughput_mbps / capacity)}
                        />
                      </td>
                    </Tr>
                  );
                })}
              </tbody>
            </Table>
          )}
        </Panel>
      </div>

      {selected && (
        <aside className="w-[380px] shrink-0 overflow-hidden border-l border-ink-800 bg-ink-900">
          <DeviceDetail
            device={selected}
            simulation={sim}
            onClose={() => selectDevice(null)}
          />
        </aside>
      )}

      <AddDeviceDialog open={adding} onClose={() => setAdding(false)} siteId={siteId} />
      <LinkDialog open={patching} onClose={() => setPatching(false)} siteId={siteId} />
    </div>
  );
}
