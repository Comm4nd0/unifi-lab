import { useState } from "react";

import {
  del,
  post,
  patch,
  useClients,
  useDevices,
  useFlows,
  useSimulation,
  useSiteMutation,
} from "@/api/client";
import { AreaChart } from "@/components/Chart";
import { PlusIcon, TrashIcon } from "@/components/icons";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Meter,
  Modal,
  Panel,
  Select,
  Table,
  Toggle,
  Tr,
  cx,
  useToast,
} from "@/components/ui";
import { loadTone, mbps, percent, speed } from "@/lib/format";
import { useUi } from "@/store";
import type { FlowRow, SimFlowResult } from "@/types";

export function TrafficPage() {
  const { siteId } = useUi();
  const { data: sim } = useSimulation(siteId);
  const flows = useFlows(siteId);
  const toast = useToast();
  const [adding, setAdding] = useState(false);

  const remove = useSiteMutation(siteId, (id: number) => del(`/flows/${id}/`));
  const toggle = useSiteMutation(siteId, (args: { id: number; enabled: boolean }) =>
    patch(`/flows/${args.id}/`, { enabled: args.enabled }),
  );

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading traffic…</div>;

  const byId = new Map<string, SimFlowResult>(
    sim.traffic.flows.map((flow) => [flow.id, flow]),
  );

  return (
    <div className="space-y-4 p-5">
      <Panel
        title="Internet throughput"
        subtitle="Last 60 seconds of simulated traffic"
      >
        <AreaChart
          height={150}
          series={[
            {
              name: "Download",
              color: "#1f7aff",
              values: sim.traffic.history.map((point) => point.download_mbps),
            },
            {
              name: "Upload",
              color: "#2fb87a",
              values: sim.traffic.history.map((point) => point.upload_mbps),
            },
          ]}
        />
      </Panel>

      <Panel
        title="Traffic generators"
        subtitle="Synthetic flows placed onto the forwarding topology"
        bodyClassName="p-0"
        action={
          <Button size="sm" variant="primary" onClick={() => setAdding(true)}>
            <PlusIcon size={14} /> Add flow
          </Button>
        }
      >
        {!flows.data?.length ? (
          <EmptyState
            title="No flows defined"
            detail="Clients already generate background traffic. Add a flow to model a backup, a camera stream or a file copy."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                Add a flow
              </Button>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <th className="th">Flow</th>
                <th className="th">Path</th>
                <th className="th text-right">Offered</th>
                <th className="th text-right">Delivered</th>
                <th className="th text-right">Loss</th>
                <th className="th text-right">Latency</th>
                <th className="th">Status</th>
                <th className="th" />
              </tr>
            </thead>
            <tbody>
              {flows.data.map((flow) => {
                const result = byId.get(`flow:${flow.id}`);
                const path = (result?.path_device_ids ?? [])
                  .map((id) => sim.devices.find((device) => device.id === id)?.name ?? id)
                  .join(" → ");
                return (
                  <Tr key={flow.id}>
                    <td className="td">
                      <div className="font-medium text-ink-100">{flow.name}</div>
                      <div className="text-xs text-ink-500">
                        {flow.protocol.toUpperCase()} · {flow.mbps} Mbps target
                      </div>
                    </td>
                    <td className="td max-w-[260px] truncate text-xs text-ink-400">
                      {path || "no path"}
                    </td>
                    <td className="td text-right tabular-nums">
                      {mbps(result?.offered_mbps ?? 0)}
                    </td>
                    <td className="td text-right tabular-nums">
                      {mbps(result?.delivered_mbps ?? 0)}
                    </td>
                    <td
                      className={cx(
                        "td text-right tabular-nums",
                        (result?.loss_pct ?? 0) > 0 && "text-warn",
                      )}
                    >
                      {(result?.loss_pct ?? 0).toFixed(1)}%
                    </td>
                    <td className="td text-right tabular-nums text-ink-400">
                      {(result?.latency_ms ?? 0).toFixed(1)} ms
                    </td>
                    <td className="td">
                      {!flow.enabled ? (
                        <Badge>paused</Badge>
                      ) : (
                        <Badge
                          tone={
                            result?.status === "ok"
                              ? "ok"
                              : result?.status === "congested"
                                ? "warn"
                                : "bad"
                          }
                        >
                          {result?.status ?? "dropped"}
                        </Badge>
                      )}
                    </td>
                    <td className="td text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          className="text-xs text-ink-400 hover:text-ink-100"
                          onClick={() =>
                            toggle.mutate({ id: flow.id, enabled: !flow.enabled })
                          }
                        >
                          {flow.enabled ? "Pause" : "Resume"}
                        </button>
                        <button
                          className="text-ink-500 hover:text-bad"
                          onClick={() =>
                            remove
                              .mutateAsync(flow.id)
                              .then(() => toast("Flow removed."))
                              .catch((error: Error) => toast(error.message, "bad"))
                          }
                        >
                          <TrashIcon size={15} />
                        </button>
                      </div>
                    </td>
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel title="Link utilisation" bodyClassName="p-0">
        <Table>
          <thead>
            <tr>
              <th className="th">Link</th>
              <th className="th">Speed</th>
              <th className="th">State</th>
              <th className="th text-right">Load</th>
              <th className="th w-48">Utilisation</th>
            </tr>
          </thead>
          <tbody>
            {sim.links.map((link) => (
              <Tr key={link.id}>
                <td className="td">
                  <div className="text-ink-100">{link.a_label}</div>
                  <div className="text-xs text-ink-500">→ {link.b_label}</div>
                </td>
                <td className="td text-ink-400">{speed(link.speed_mbps)}</td>
                <td className="td">
                  <Badge
                    tone={
                      link.storm
                        ? "bad"
                        : link.state === "forwarding"
                          ? "ok"
                          : link.state === "blocked"
                            ? "warn"
                            : "neutral"
                    }
                  >
                    {link.storm ? "storm" : link.state}
                  </Badge>
                </td>
                <td className="td text-right tabular-nums">{mbps(link.load_mbps)}</td>
                <td className="td">
                  <div className="mb-1 text-xs tabular-nums text-ink-400">
                    {percent(link.utilisation)}
                  </div>
                  <Meter value={link.utilisation} tone={loadTone(link.utilisation)} />
                </td>
              </Tr>
            ))}
            {!sim.links.length && (
              <tr>
                <td className="td text-ink-500" colSpan={5}>
                  No cables patched yet.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
      </Panel>

      <AddFlowDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}

function AddFlowDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const { siteId } = useUi();
  const clients = useClients(siteId);
  const devices = useDevices(siteId);
  const [form, setForm] = useState({
    name: "",
    mbps: 100,
    protocol: "tcp",
    src: "internet:internet",
    dst: "internet:internet",
    enabled: true,
  });

  const endpoints = [
    { value: "internet:internet", label: "Internet" },
    ...(clients.data ?? []).map((client) => ({
      value: `client:${client.id}`,
      label: `Client · ${client.name}`,
    })),
    ...(devices.data ?? []).map((device) => ({
      value: `device:${device.id}`,
      label: `Device · ${device.name}`,
    })),
  ];

  const split = (value: string) => {
    const [kind, id] = value.split(":");
    return {
      kind,
      client: kind === "client" ? Number(id) : null,
      device: kind === "device" ? Number(id) : null,
    };
  };

  const create = useSiteMutation(siteId, () => {
    const src = split(form.src);
    const dst = split(form.dst);
    return post<FlowRow>("/flows/", {
      site: siteId,
      name: form.name.trim(),
      mbps: form.mbps,
      protocol: form.protocol,
      enabled: form.enabled,
      src_kind: src.kind,
      src_client: src.client,
      src_device: src.device,
      dst_kind: dst.kind,
      dst_client: dst.client,
      dst_device: dst.device,
    });
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a traffic flow"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!form.name.trim() || form.src === form.dst || create.isPending}
            onClick={() =>
              create
                .mutateAsync()
                .then(() => {
                  toast("Flow started.");
                  onClose();
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Start flow
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Name">
          <Input
            autoFocus
            placeholder="Nightly backup"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="From">
            <Select
              value={form.src}
              onChange={(event) => setForm({ ...form, src: event.target.value })}
            >
              {endpoints.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="To">
            <Select
              value={form.dst}
              onChange={(event) => setForm({ ...form, dst: event.target.value })}
            >
              {endpoints.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Rate (Mbps)">
            <Input
              type="number"
              min={1}
              value={form.mbps}
              onChange={(event) => setForm({ ...form, mbps: Number(event.target.value) })}
            />
          </Field>
          <Field label="Protocol">
            <Select
              value={form.protocol}
              onChange={(event) => setForm({ ...form, protocol: event.target.value })}
            >
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
            </Select>
          </Field>
        </div>
        <Toggle
          label="Start immediately"
          checked={form.enabled}
          onChange={(enabled) => setForm({ ...form, enabled })}
        />
      </div>
    </Modal>
  );
}
