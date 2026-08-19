import { useEffect, useMemo, useState } from "react";

import {
  del,
  post,
  useClients,
  useDevices,
  useSimulation,
  useSiteMutation,
} from "@/api/client";
import { PlusIcon, TrashIcon } from "@/components/icons";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Modal,
  Panel,
  Select,
  StatusDot,
  Table,
  Tr,
  useToast,
} from "@/components/ui";
import { mbps } from "@/lib/format";
import { useUi } from "@/store";
import type { ClientRow, DeviceRow, LinkRow, PortRow } from "@/types";

const CATEGORIES = [
  "workstation",
  "laptop",
  "phone",
  "tablet",
  "tv",
  "server",
  "camera",
  "printer",
  "voip",
  "iot",
];

export function ClientsPage() {
  const { siteId } = useUi();
  const { data: sim } = useSimulation(siteId);
  const clients = useClients(siteId);
  const toast = useToast();
  const [adding, setAdding] = useState(false);

  const remove = useSiteMutation(siteId, (id: number) => del(`/clients/${id}/`));

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading clients…</div>;

  return (
    <div className="p-5">
      <Panel
        title="Clients"
        subtitle={`${sim.clients.length} attached`}
        bodyClassName="p-0"
        action={
          <Button size="sm" variant="primary" onClick={() => setAdding(true)}>
            <PlusIcon size={14} /> Add client
          </Button>
        }
      >
        {sim.clients.length === 0 ? (
          <EmptyState
            title="No clients yet"
            detail="Add a laptop, a camera or a NAS and give it a traffic profile."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                Add a client
              </Button>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <th className="th">Name</th>
                <th className="th">Connection</th>
                <th className="th">IP</th>
                <th className="th">MAC</th>
                <th className="th text-right">Down</th>
                <th className="th text-right">Up</th>
                <th className="th" />
              </tr>
            </thead>
            <tbody>
              {sim.clients.map((client) => {
                const row = clients.data?.find((item) => String(item.id) === client.id);
                return (
                  <Tr key={client.id}>
                    <td className="td">
                      <div className="flex items-center gap-2">
                        <StatusDot status={client.status} />
                        <span className="font-medium text-ink-100">{client.name}</span>
                        <Badge>{client.category}</Badge>
                      </div>
                    </td>
                    <td className="td text-ink-400">
                      {client.kind === "wireless" ? (
                        <>
                          {client.device_name ?? "unassociated"}
                          {client.rssi_dbm !== null && (
                            <span className="ml-2 text-xs text-ink-500">
                              {client.rssi_dbm} dBm
                            </span>
                          )}
                        </>
                      ) : (
                        <>
                          {client.device_name ?? "unplugged"}
                          {client.port_label && (
                            <span className="ml-2 text-xs text-ink-500">
                              {client.port_label}
                            </span>
                          )}
                        </>
                      )}
                    </td>
                    <td className="td font-mono text-xs text-ink-400">{client.ip || "—"}</td>
                    <td className="td font-mono text-xs text-ink-500">{client.mac}</td>
                    <td className="td text-right tabular-nums">{mbps(client.down_mbps)}</td>
                    <td className="td text-right tabular-nums">{mbps(client.up_mbps)}</td>
                    <td className="td text-right">
                      {row && (
                        <button
                          className="text-ink-500 hover:text-bad"
                          title={`Remove ${client.name}`}
                          onClick={() =>
                            remove
                              .mutateAsync(row.id)
                              .then(() => toast(`${client.name} removed.`))
                              .catch((error: Error) => toast(error.message, "bad"))
                          }
                        >
                          <TrashIcon size={15} />
                        </button>
                      )}
                    </td>
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Panel>

      <AddClientDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}

function AddClientDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const { siteId } = useUi();
  const devices = useDevices(siteId);
  const [form, setForm] = useState({
    name: "",
    kind: "wired" as "wired" | "wireless",
    category: "workstation",
    port: "",
    access_point: "",
    down_mbps: 25,
    up_mbps: 5,
  });

  useEffect(() => {
    if (open) setForm((current) => ({ ...current, name: "", port: "", access_point: "" }));
  }, [open]);

  const accessPoints = (devices.data ?? []).filter(
    (device) => device.line === "ap" || device.model.startsWith("udm") || device.model === "ux",
  );
  const freePorts = useFreeAccessPorts(devices.data ?? []);

  const create = useSiteMutation(siteId, () =>
    post<ClientRow>("/clients/", {
      site: siteId,
      name: form.name.trim(),
      kind: form.kind,
      category: form.category,
      port: form.kind === "wired" && form.port ? Number(form.port) : null,
      access_point:
        form.kind === "wireless" && form.access_point ? Number(form.access_point) : null,
      down_mbps: form.down_mbps,
      up_mbps: form.up_mbps,
    }),
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a client"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!form.name.trim() || create.isPending}
            onClick={() =>
              create
                .mutateAsync()
                .then(() => {
                  toast(`${form.name} joined the network.`);
                  onClose();
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Add
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Name">
          <Input
            autoFocus
            value={form.name}
            placeholder="Workshop laptop"
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Connection">
            <Select
              value={form.kind}
              onChange={(event) =>
                setForm({ ...form, kind: event.target.value as "wired" | "wireless" })
              }
            >
              <option value="wired">Wired</option>
              <option value="wireless">Wireless</option>
            </Select>
          </Field>
          <Field label="Type">
            <Select
              value={form.category}
              onChange={(event) => setForm({ ...form, category: event.target.value })}
            >
              {CATEGORIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {form.kind === "wired" ? (
          <Field label="Switch port" hint="Only free ports are listed">
            <Select
              value={form.port}
              onChange={(event) => setForm({ ...form, port: event.target.value })}
            >
              <option value="">Not plugged in</option>
              {freePorts.map(({ device, port }) => (
                <option key={port.id} value={port.id}>
                  {device.name} · {port.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="Access point">
            <Select
              value={form.access_point}
              onChange={(event) => setForm({ ...form, access_point: event.target.value })}
            >
              <option value="">Not associated</option>
              {accessPoints.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name}
                </option>
              ))}
            </Select>
          </Field>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Field label="Download (Mbps)">
            <Input
              type="number"
              min={0}
              value={form.down_mbps}
              onChange={(event) => setForm({ ...form, down_mbps: Number(event.target.value) })}
            />
          </Field>
          <Field label="Upload (Mbps)">
            <Input
              type="number"
              min={0}
              value={form.up_mbps}
              onChange={(event) => setForm({ ...form, up_mbps: Number(event.target.value) })}
            />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

/** Ports with no cable in them — where a client could plausibly be plugged. */
function useFreeAccessPorts(devices: DeviceRow[]) {
  const { siteId } = useUi();
  const { data: sim } = useSimulation(siteId);
  return useMemo(() => {
    const patched = new Set<string>();
    for (const link of sim?.links ?? ([] as LinkRow[] & never[])) {
      patched.add(link.a_port_id);
      patched.add(link.b_port_id);
    }
    const rows: { device: DeviceRow; port: PortRow }[] = [];
    for (const device of devices) {
      for (const port of device.ports) {
        if (port.role === "wan") continue;
        if (patched.has(`${device.id}:${port.index}`)) continue;
        rows.push({ device, port });
      }
    }
    return rows;
  }, [devices, sim?.links]);
}
