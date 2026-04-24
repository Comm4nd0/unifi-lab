import { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/toast";
import { FlowRateChart } from "../components/FlowRateChart";
import { PortMap } from "../components/PortMap";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";
import { profileFor } from "../lib/deviceModels";

type Tab = "overview" | "ports" | "radios" | "flows" | "simulate";

export function DeviceDetailPage() {
  const { id } = useParams({ from: "/_app/devices/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [tab, setTab] = useState<Tab>("overview");

  const toast = useToast();
  const { openConfirm } = useConfirm();

  const device = useQuery({
    queryKey: ["devices", id],
    queryFn: () => endpoints.devices.get(id),
    refetchInterval: 5_000,
  });

  const del = useMutation({
    mutationFn: () => endpoints.devices.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      navigate({ to: "/devices" });
    },
    onError: (err) => toast.error(`Delete failed: ${(err as Error).message}`),
  });

  const force = useMutation({
    mutationFn: () => endpoints.devices.forceInform(id),
  });
  const disconnect = useMutation({
    mutationFn: () => endpoints.devices.disconnect(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices", id] }),
  });
  const reconnect = useMutation({
    mutationFn: () => endpoints.devices.reconnect(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices", id] }),
  });

  if (device.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (device.error) return <p className="text-sm text-red-400">{(device.error as Error).message}</p>;
  if (!device.data) return null;

  const d = device.data;
  const profile = profileFor(d.model_code);

  const tabs: { id: Tab; label: string; available: boolean }[] = [
    { id: "overview", label: "Overview", available: true },
    { id: "ports", label: "Ports", available: !!profile.ports?.length },
    { id: "radios", label: "Radios", available: !!profile.radios?.length },
    { id: "flows", label: "Flows", available: true },
    { id: "simulate", label: "Simulate", available: true },
  ];

  return (
    <>
      <PageHeader
        title={d.hostname || d.mac_address}
        subtitle={`${d.mac_address} · ${d.model_code} · ${d.firmware_version || "unversioned"}`}
        actions={
          <>
            <Link to="/devices" className="text-sm text-slate-400 hover:text-white">
              ← All devices
            </Link>
            <Link
              to="/devices/$id/inform"
              params={{ id: d.id }}
              className="inline-flex h-8 items-center rounded-md bg-slate-800 px-3 text-sm text-slate-100 hover:bg-slate-700 border border-slate-700"
            >
              Inform Inspector →
            </Link>
            <Button
              variant="danger"
              size="sm"
              onClick={async () => {
                const ok = await openConfirm({
                  title: `Delete ${d.mac_address}?`,
                  message: "The device record will be removed from the engine.",
                  confirmLabel: "Delete",
                  variant: "danger",
                });
                if (ok) del.mutate();
              }}
              disabled={del.isPending}
            >
              Delete
            </Button>
          </>
        }
      />

      <nav className="mb-6 flex gap-1 border-b border-slate-800">
        {tabs
          .filter((t) => t.available)
          .map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={
                "-mb-px border-b-2 px-4 py-2 text-sm transition " +
                (tab === t.id
                  ? "border-indigo-500 text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200")
              }
            >
              {t.label}
            </button>
          ))}
      </nav>

      {tab === "overview" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Identity</h3>
            <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">Hostname</dt>
              <dd>{d.hostname || <span className="text-slate-600">—</span>}</dd>
              <dt className="text-slate-500">MAC</dt>
              <dd className="font-mono text-xs">{d.mac_address}</dd>
              <dt className="text-slate-500">Serial</dt>
              <dd className="font-mono text-xs">{d.serial_number}</dd>
              <dt className="text-slate-500">Model</dt>
              <dd>{d.model_code}</dd>
              <dt className="text-slate-500">Family</dt>
              <dd className="font-mono text-xs">{profile.family}</dd>
              <dt className="text-slate-500">Firmware</dt>
              <dd>{d.firmware_version || "—"}</dd>
              <dt className="text-slate-500">State</dt>
              <dd>
                <StateChip state={d.state} />
              </dd>
            </dl>
          </Card>

          <Card>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Runtime</h3>
            <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">Controller</dt>
              <dd>
                {d.controller_target ? (
                  <Link
                    to="/controllers/$id"
                    params={{ id: d.controller_target }}
                    className="font-mono text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    {d.controller_target}
                  </Link>
                ) : (
                  <span className="text-slate-600">unassigned</span>
                )}
              </dd>
              <dt className="text-slate-500">Fleet</dt>
              <dd>
                {d.fleet ? (
                  <Link
                    to="/fleets/$id"
                    params={{ id: d.fleet }}
                    className="font-mono text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    {d.fleet}
                  </Link>
                ) : (
                  <span className="text-slate-600">none</span>
                )}
              </dd>
              <dt className="text-slate-500">Last heartbeat</dt>
              <dd className="font-mono text-xs">
                {d.last_heartbeat_at ? new Date(d.last_heartbeat_at).toLocaleString() : "never"}
              </dd>
              <dt className="text-slate-500">Last config</dt>
              <dd className="font-mono text-xs">
                {d.last_config_applied_at
                  ? new Date(d.last_config_applied_at).toLocaleString()
                  : "never"}
              </dd>
              <dt className="text-slate-500">Created</dt>
              <dd className="font-mono text-xs text-slate-400">
                {new Date(d.created_at).toLocaleString()}
              </dd>
            </dl>
          </Card>
        </div>
      )}

      {tab === "ports" && (
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Physical ports
          </h3>
          <p className="mt-2 text-xs text-slate-500">
            Port state is static until the Phase-0 inform codec lands — clicks are a no-op for now.
          </p>
          <div className="mt-4">
            <PortMap modelCode={d.model_code} />
          </div>
        </Card>
      )}

      {tab === "radios" && (
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Radios</h3>
          {(profile.radios ?? []).length === 0 ? (
            <EmptyState title="No radios on this model" />
          ) : (
            <ul className="mt-3 grid gap-3 md:grid-cols-2">
              {(profile.radios ?? []).map((r) => (
                <li
                  key={r.name}
                  className="rounded-md border border-slate-800 bg-slate-950 p-4 text-sm"
                >
                  <p className="text-slate-200 font-medium">{r.name}</p>
                  <p className="mt-1 text-xs text-slate-400">Band: {r.band}</p>
                  <p className="mt-2 text-xs text-slate-600">
                    Channel / power / clients populate once the protocol codec transmits real
                    telemetry.
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {tab === "flows" && <DeviceFlowsTab deviceId={d.id} />}

      {tab === "simulate" && (
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Simulate events
          </h3>
          <p className="mt-2 text-xs text-slate-500">
            These map to worker-side events the supervisor reacts to. No bytes transmitted until
            the inform codec is real.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => force.mutate()}
              disabled={force.isPending}
            >
              {force.isPending ? "Sending…" : "Force inform"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending || d.state === "disconnected"}
            >
              Disconnect
            </Button>
            <Button
              variant="secondary"
              onClick={() => reconnect.mutate()}
              disabled={reconnect.isPending || d.state !== "disconnected"}
            >
              Reconnect
            </Button>
          </div>

          {(force.isSuccess || disconnect.isSuccess || reconnect.isSuccess) && (
            <p className="mt-4 text-sm text-emerald-300">
              Event accepted — the page auto-refreshes every 5s to pick up state changes.
            </p>
          )}
          {(force.error || disconnect.error || reconnect.error) && (
            <p className="mt-4 text-sm text-red-400">
              Action failed:{" "}
              {(force.error || disconnect.error || reconnect.error) instanceof Error
                ? ((force.error || disconnect.error || reconnect.error) as Error).message
                : "unknown"}
            </p>
          )}
        </Card>
      )}
    </>
  );
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function DeviceFlowsTab({ deviceId }: { deviceId: string }) {
  const stats = useQuery({
    queryKey: ["traffic", "flows", "stats", { device: deviceId }],
    queryFn: () =>
      endpoints.traffic.stats({
        device: deviceId,
        window_minutes: 60,
        bucket_seconds: 60,
      }),
    refetchInterval: 5_000,
  });
  // The flows list endpoint filters by fleet; for a single-device view we
  // pull a page of recent flows and narrow client-side. Cheaper than
  // adding a dedicated filter until we grow a dashboard.
  const flows = useQuery({
    queryKey: ["traffic", "flows", "byDevice", deviceId],
    queryFn: () => endpoints.traffic.flows(),
    refetchInterval: 5_000,
    select: (d) => ({
      ...d,
      results: d.results.filter((f) => f.device === deviceId).slice(0, 20),
    }),
  });

  const deviceTotals = stats.data?.totals;

  return (
    <div className="grid gap-4">
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Flow rate — last hour
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {deviceTotals
                ? `${deviceTotals.allowed.toLocaleString()} allowed · ${deviceTotals.blocked.toLocaleString()} blocked · ${humanBytes(
                    deviceTotals.bytes_tx + deviceTotals.bytes_rx,
                  )} total`
                : "Loading…"}
            </p>
          </div>
        </div>
        {stats.data && (
          <div className="mt-3">
            <FlowRateChart stats={stats.data} />
          </div>
        )}
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="border-b border-slate-800 px-4 py-3">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Recent flows
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Latest 20 flow records observed for this device. Refreshes every 5s.
          </p>
        </div>
        {flows.isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
        {flows.data && flows.data.results.length === 0 && (
          <EmptyState
            title="No flows yet"
            hint="Attach this device to a fleet with an active traffic profile, or generate samples from the Traffic tab."
          />
        )}
        {flows.data && flows.data.results.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-3 py-2 text-left font-medium">App</th>
                <th className="px-3 py-2 text-left font-medium">Proto</th>
                <th className="px-3 py-2 text-left font-medium">Dest</th>
                <th className="px-3 py-2 text-right font-medium">Tx</th>
                <th className="px-3 py-2 text-right font-medium">Rx</th>
                <th className="px-3 py-2 text-left font-medium">State</th>
                <th className="px-3 py-2 text-left font-medium">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {flows.data.results.map((f) => (
                <tr key={f.id} className={f.blocked ? "bg-red-950/30" : "hover:bg-slate-900/40"}>
                  <td className="px-3 py-2">
                    {f.application || <span className="text-slate-600">—</span>}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs uppercase">{f.protocol}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {f.dst_ip}
                    {f.dst_port ? `:${f.dst_port}` : ""}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-400">
                    {humanBytes(f.bytes_tx)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-400">
                    {humanBytes(f.bytes_rx)}
                  </td>
                  <td className="px-3 py-2">
                    <StateChip state={f.blocked ? "error" : "ok"} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {new Date(f.reported_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
