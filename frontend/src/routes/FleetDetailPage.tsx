import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { useChannel } from "../api/ws";
import { useConfirm } from "../components/ConfirmDialog";
import { FlowRateChart } from "../components/FlowRateChart";
import { useToast } from "../components/toast";
import { TopologyGraph } from "../components/TopologyGraph";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

type Tab = "overview" | "topology" | "devices" | "traffic";

const READY_STATES = new Set(["adopted", "heartbeat"]);

function rampProgress(deviceStates: Record<string, number>, deviceCount: number): number {
  if (!deviceCount) return 0;
  let ready = 0;
  for (const [state, count] of Object.entries(deviceStates)) {
    if (READY_STATES.has(state)) ready += count;
  }
  return Math.min(100, Math.round((ready / deviceCount) * 100));
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>Ramp progress</span>
        <span className="font-mono">{percent}%</span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-emerald-500 transition-[width] duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function humanBytes(n: number): string {
  if (n < 1_000) return `${n} B`;
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)} KB`;
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(1)} MB`;
  return `${(n / 1_000_000_000).toFixed(2)} GB`;
}

export function FleetDetailPage() {
  const { id } = useParams({ from: "/_app/fleets/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [tab, setTab] = useState<Tab>("overview");

  const toast = useToast();
  const { openConfirm } = useConfirm();

  const fleet = useQuery({
    queryKey: ["fleets", id],
    queryFn: () => endpoints.fleets.get(id),
  });
  const devices = useQuery({ queryKey: ["devices"], queryFn: endpoints.devices.list });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });

  // Live push via the fleet channel.
  const { state: wsState, messages } = useChannel({ path: `/ws/fleets/${id}/` });

  // Invalidate fleet + device queries whenever a new WS event arrives so
  // the device_states breakdown and row statuses stay fresh without polling.
  const lastSeenCount = useRef(0);
  useEffect(() => {
    if (messages.length > lastSeenCount.current) {
      lastSeenCount.current = messages.length;
      qc.invalidateQueries({ queryKey: ["fleets", id] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    }
  }, [messages.length, id, qc]);

  const blueprint = useQuery({
    queryKey: ["blueprints", fleet.data?.blueprint],
    queryFn: () => endpoints.blueprints.get(fleet.data!.blueprint!),
    enabled: !!fleet.data?.blueprint,
  });

  const trafficStats = useQuery({
    queryKey: ["traffic", "flows", "stats", { fleet: id }],
    queryFn: () =>
      endpoints.traffic.stats({ fleet: id, window_minutes: 60, bucket_seconds: 60 }),
    refetchInterval: 5_000,
  });

  const pause = useMutation({
    mutationFn: () => endpoints.fleets.pause(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fleets", id] }),
  });
  const resume = useMutation({
    mutationFn: () => endpoints.fleets.resume(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fleets", id] }),
  });
  const tear = useMutation({
    mutationFn: () => endpoints.fleets.teardown(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fleets"] });
      qc.invalidateQueries({ queryKey: ["devices"] });
      navigate({ to: "/fleets", search: { blueprint: undefined } });
    },
    onError: (err) => toast.error(`Tear-down failed: ${(err as Error).message}`),
  });
  const startTraffic = useMutation({
    mutationFn: () => endpoints.fleets.startTraffic(id),
    onSuccess: () => toast.success("Traffic profiles activated"),
    onError: (err) => toast.error(`Start failed: ${(err as Error).message}`),
  });
  const stopTraffic = useMutation({
    mutationFn: () => endpoints.fleets.stopTraffic(id),
    onSuccess: () => toast.success("Traffic profiles deactivated"),
    onError: (err) => toast.error(`Stop failed: ${(err as Error).message}`),
  });

  if (fleet.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (fleet.error) return <p className="text-sm text-red-400">{(fleet.error as Error).message}</p>;
  if (!fleet.data) return null;

  const f = fleet.data;
  const ctrl = controllers.data?.results.find((c) => c.id === f.controller_target);
  const related = devices.data?.results.filter((d) => d.fleet === f.id) ?? [];
  const blueprintIdForLink = f.blueprint;
  const stateEntries = Object.entries(f.device_states ?? {});
  const busy = pause.isPending || resume.isPending || tear.isPending;
  const showProgress =
    f.device_count > 0 && (f.state === "ramping" || f.state === "active");
  const percent = rampProgress(f.device_states ?? {}, f.device_count);

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "topology", label: "Topology" },
    { id: "devices", label: `Devices (${related.length})` },
    { id: "traffic", label: "Traffic" },
  ];

  return (
    <>
      <PageHeader
        title={f.name}
        subtitle={`${f.device_count} × ${f.model_code}`}
        actions={
          <>
            <Link to="/fleets" search={{ blueprint: undefined }} className="text-sm text-slate-400 hover:text-white">
              ← All fleets
            </Link>
            {f.state !== "paused" && (
              <Button size="sm" variant="secondary" onClick={() => pause.mutate()} disabled={busy}>
                Pause
              </Button>
            )}
            {f.state === "paused" && (
              <Button size="sm" variant="secondary" onClick={() => resume.mutate()} disabled={busy}>
                Resume
              </Button>
            )}
            <Button
              size="sm"
              variant="danger"
              onClick={async () => {
                const ok = await openConfirm({
                  title: `Tear down "${f.name}"?`,
                  message: "All devices in this fleet will be despawned.",
                  confirmLabel: "Tear down",
                  variant: "danger",
                });
                if (ok) tear.mutate();
              }}
              disabled={busy}
            >
              Tear down
            </Button>
          </>
        }
      />

      <nav className="mb-6 flex gap-1 border-b border-slate-800">
        {tabs.map((t) => (
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
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <span>Live:</span>
          <StateChip state={wsState} />
        </div>
      </nav>

      {tab === "overview" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Fleet</h3>
            <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">State</dt>
              <dd>
                <StateChip state={f.state} />
              </dd>
              <dt className="text-slate-500">Controller</dt>
              <dd>
                {ctrl ? (
                  <Link
                    to="/controllers/$id"
                    params={{ id: ctrl.id }}
                    className="text-indigo-400 hover:text-indigo-300"
                  >
                    {ctrl.name}
                  </Link>
                ) : (
                  <span className="text-slate-600">—</span>
                )}
              </dd>
              <dt className="text-slate-500">Source</dt>
              <dd>
                {blueprintIdForLink ? (
                  <Link
                    to="/blueprints/$id"
                    params={{ id: blueprintIdForLink }}
                    className="text-indigo-400 hover:text-indigo-300"
                  >
                    Blueprint
                  </Link>
                ) : (
                  <span className="font-mono text-xs">{f.model_code} (simple)</span>
                )}
              </dd>
              <dt className="text-slate-500">Device count</dt>
              <dd className="font-mono text-xs">{f.device_count}</dd>
              <dt className="text-slate-500">Auto-adopt</dt>
              <dd>{f.auto_adopt ? "yes" : "no"}</dd>
              <dt className="text-slate-500">Retired at</dt>
              <dd className="font-mono text-xs">
                {f.retired_at ? new Date(f.retired_at).toLocaleString() : "—"}
              </dd>
              <dt className="text-slate-500">Created</dt>
              <dd className="font-mono text-xs text-slate-400">
                {new Date(f.created_at).toLocaleString()}
              </dd>
            </dl>
            {showProgress && <ProgressBar percent={percent} />}
          </Card>

          <Card>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Device state breakdown
            </h3>
            {stateEntries.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No devices provisioned.</p>
            ) : (
              <ul className="mt-3 flex flex-wrap gap-2">
                {stateEntries.map(([state, count]) => (
                  <li key={state} className="flex items-center gap-2 text-sm">
                    <StateChip state={state} />
                    <span className="font-mono text-slate-300">× {count}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Live activity feed during deployment */}
          {messages.length > 0 && (
            <Card className="md:col-span-2">
              <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
                Live activity
              </h3>
              <div className="mt-3 max-h-48 overflow-y-auto">
                <ul className="space-y-1.5">
                  {[...messages].reverse().slice(0, 20).map((msg, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 text-xs"
                    >
                      <span className="font-mono text-slate-600">
                        {new Date(msg.ts).toLocaleTimeString()}
                      </span>
                      <StateChip state={msg.type.split(".").pop() || msg.type} />
                      <span className="text-slate-400 truncate">
                        {msg.data?.state
                          ? `Fleet → ${msg.data.state}`
                          : msg.data?.device_id
                            ? `Device ${String(msg.data.device_id).slice(0, 8)}…`
                            : JSON.stringify(msg.data).slice(0, 60)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-2 text-[10px] text-slate-600">
                {messages.length} event{messages.length !== 1 ? "s" : ""} received
              </p>
            </Card>
          )}
        </div>
      )}

      {tab === "topology" && (
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Topology</h3>
          <p className="mt-1 text-xs text-slate-500">
            Controller → devices. Blueprint-driven fleets lay out according to{" "}
            <span className="font-mono">site.devices[].uplink</span>; simple fleets fan out from
            the controller. Click a node to open the device detail.
          </p>
          <div className="mt-4">
            <TopologyGraph
              fleet={f}
              devices={related}
              parsedBlueprint={
                blueprint.data?.parsed_json as {
                  site?: { devices?: { hostname?: string; uplink?: string }[] };
                }
              }
            />
          </div>
        </Card>
      )}

      {tab === "devices" && (
        <section>
          {related.length === 0 ? (
            <EmptyState
              title="No devices yet"
              hint="Devices will appear here once the fleet finishes ramping."
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Hostname</th>
                    <th className="px-4 py-2 text-left font-medium">MAC</th>
                    <th className="px-4 py-2 text-left font-medium">Model</th>
                    <th className="px-4 py-2 text-left font-medium">State</th>
                    <th className="px-4 py-2 text-left font-medium">Last heartbeat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {related.map((d) => (
                    <tr key={d.id}>
                      <td className="px-4 py-2 text-slate-300">
                        {d.hostname || <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">
                        <Link to="/devices/$id" params={{ id: d.id }} className="hover:text-white">
                          {d.mac_address}
                        </Link>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-400">
                        {d.model_code}
                      </td>
                      <td className="px-4 py-2">
                        <StateChip state={d.state} />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-500">
                        {d.last_heartbeat_at
                          ? new Date(d.last_heartbeat_at).toLocaleString()
                          : "never"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "traffic" && (
        <div className="grid gap-4">
          <Card>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
                  Flow rate — last hour
                </h3>
                {trafficStats.data ? (
                  <p className="mt-1 text-xs text-slate-500">
                    {trafficStats.data.totals.allowed.toLocaleString()} allowed ·{" "}
                    {trafficStats.data.totals.blocked.toLocaleString()} blocked ·{" "}
                    {humanBytes(trafficStats.data.totals.bytes_tx + trafficStats.data.totals.bytes_rx)} total
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">Loading…</p>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => startTraffic.mutate()}
                  disabled={startTraffic.isPending || stopTraffic.isPending}
                >
                  {startTraffic.isPending ? "Starting…" : "▶ Start traffic"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => stopTraffic.mutate()}
                  disabled={startTraffic.isPending || stopTraffic.isPending}
                >
                  {stopTraffic.isPending ? "Stopping…" : "⏹ Stop traffic"}
                </Button>
              </div>
            </div>
            {trafficStats.data && (
              <div className="mt-3">
                <FlowRateChart stats={trafficStats.data} height={96} />
              </div>
            )}
          </Card>

          {trafficStats.data && (
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Allowed</p>
                <p className="mt-2 text-2xl font-semibold text-emerald-300">
                  {trafficStats.data.totals.allowed.toLocaleString()}
                </p>
              </Card>
              <Card>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Blocked</p>
                <p className="mt-2 text-2xl font-semibold text-rose-300">
                  {trafficStats.data.totals.blocked.toLocaleString()}
                </p>
              </Card>
              <Card>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">TX</p>
                <p className="mt-2 text-2xl font-semibold text-slate-100">
                  {humanBytes(trafficStats.data.totals.bytes_tx)}
                </p>
              </Card>
              <Card>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">RX</p>
                <p className="mt-2 text-2xl font-semibold text-slate-100">
                  {humanBytes(trafficStats.data.totals.bytes_rx)}
                </p>
              </Card>
            </div>
          )}
        </div>
      )}
    </>
  );
}
