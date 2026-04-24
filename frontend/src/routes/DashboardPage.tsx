import { useEffect, useRef } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints, type VirtualDevice } from "../api/client";
import { useChannel } from "../api/ws";
import { FlowRateChart } from "../components/FlowRateChart";
import { Card, EmptyState, PageHeader, StateChip } from "../components/ui";

const READY_STATES = new Set(["adopted", "heartbeat"]);

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function humanRelative(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  if (delta < 60_000) return "just now";
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
  if (delta < 86_400_000) return `${Math.round(delta / 3_600_000)}h ago`;
  return `${Math.round(delta / 86_400_000)}d ago`;
}

function Kpi({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "good" | "warn";
}) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={
          "mt-2 text-3xl font-semibold " +
          (tone === "good"
            ? "text-emerald-300"
            : tone === "warn"
              ? "text-amber-300"
              : "text-slate-100")
        }
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </Card>
  );
}

export function DashboardPage() {
  const qc = useQueryClient();
  const { state: wsState, messages } = useChannel({ path: "/ws/cluster/" });

  // The cluster socket receives a copy of every fleet event. On each
  // new message we invalidate the queries that likely need refreshing
  // so the dashboard stays live without tight polling. We still keep
  // a slow refetchInterval as a safety net for missed events.
  const lastSeenCount = useRef(0);
  useEffect(() => {
    if (messages.length <= lastSeenCount.current) return;
    lastSeenCount.current = messages.length;
    qc.invalidateQueries({ queryKey: ["fleets"] });
    qc.invalidateQueries({ queryKey: ["devices"] });
    qc.invalidateQueries({ queryKey: ["audit", "recent"] });
  }, [messages.length, qc]);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: endpoints.health,
    refetchInterval: 30_000,
  });
  const workerStatus = useQuery({
    queryKey: ["worker-status"],
    queryFn: endpoints.workerStatus,
    refetchInterval: 15_000,
  });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });
  const devices = useQuery({
    queryKey: ["devices"],
    queryFn: endpoints.devices.list,
    refetchInterval: 30_000,
  });
  const fleets = useQuery({
    queryKey: ["fleets"],
    queryFn: endpoints.fleets.list,
    refetchInterval: 30_000,
  });
  const stats = useQuery({
    queryKey: ["traffic", "flows", "stats", "cluster"],
    queryFn: () =>
      endpoints.traffic.stats({ window_minutes: 60, bucket_seconds: 60 }),
    refetchInterval: 5_000,
  });
  const audit = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => endpoints.audit.list({ page_size: 8 }),
    refetchInterval: 15_000,
  });

  const devicesTotal = devices.data?.count ?? 0;
  const devicesByState = (devices.data?.results ?? []).reduce<Record<string, number>>(
    (acc, d: VirtualDevice) => {
      acc[d.state] = (acc[d.state] ?? 0) + 1;
      return acc;
    },
    {},
  );
  const devicesReady = Object.entries(devicesByState)
    .filter(([state]) => READY_STATES.has(state))
    .reduce((a, [, n]) => a + n, 0);
  const adoptionPct = devicesTotal > 0 ? Math.round((devicesReady / devicesTotal) * 100) : 0;

  const fleetCount = fleets.data?.count ?? 0;
  const activeFleets = (fleets.data?.results ?? []).filter(
    (f) => f.state === "active" || f.state === "ramping",
  );
  const rampingFleets = activeFleets.filter((f) => f.state === "ramping");

  const flowTotals = stats.data?.totals;
  const flowsPerMin = flowTotals
    ? Math.round(((flowTotals.allowed + flowTotals.blocked) / (stats.data!.window_minutes || 1)) * 10) / 10
    : 0;
  const bytesLastHour = flowTotals ? flowTotals.bytes_tx + flowTotals.bytes_rx : 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Live cluster state — updates on fleet events over WebSocket."
        actions={
          <span className="flex items-center gap-2 text-xs text-slate-400">
            <span>Live:</span>
            <StateChip state={wsState} />
          </span>
        }
      />

      <div className="grid gap-4 md:grid-cols-5">
        <Kpi
          label="Fleets"
          value={fleetCount}
          sub={
            activeFleets.length > 0
              ? `${activeFleets.length} active${rampingFleets.length ? ` · ${rampingFleets.length} ramping` : ""}`
              : "none active"
          }
          tone={rampingFleets.length > 0 ? "warn" : "default"}
        />
        <Kpi
          label="Devices"
          value={devicesTotal}
          sub={`${devicesReady} ready · ${adoptionPct}% adopted`}
          tone={adoptionPct === 100 ? "good" : "default"}
        />
        <Kpi
          label="Flows / min"
          value={flowsPerMin}
          sub={flowTotals ? `${humanBytes(bytesLastHour)} last hour` : "—"}
        />
        <Kpi
          label="Blocked ratio"
          value={
            flowTotals && flowTotals.allowed + flowTotals.blocked > 0
              ? `${Math.round((flowTotals.blocked / (flowTotals.allowed + flowTotals.blocked)) * 100)}%`
              : "—"
          }
          sub={
            flowTotals
              ? `${flowTotals.blocked.toLocaleString()} / ${(flowTotals.allowed + flowTotals.blocked).toLocaleString()}`
              : "last hour"
          }
          tone={flowTotals && flowTotals.blocked > 0 ? "warn" : "default"}
        />
        <Kpi
          label="Engine"
          value={
            workerStatus.data?.alive
              ? humanRelative(workerStatus.data.last_heartbeat_at ?? "")
              : workerStatus.data
                ? "dead"
                : "—"
          }
          sub={
            workerStatus.data?.alive
              ? "heartbeat ok"
              : workerStatus.data
                ? "no beat in last 90s"
                : "checking…"
          }
          tone={
            workerStatus.data?.alive ? "good" : workerStatus.data ? "warn" : "default"
          }
        />
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <Card>
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
                Cluster flow rate — last hour
              </h3>
              <Link
                to="/traffic"
                className="text-xs text-indigo-400 hover:text-indigo-300"
              >
                Open Traffic →
              </Link>
            </div>
            {stats.data ? (
              <div className="mt-3">
                <FlowRateChart stats={stats.data} height={96} />
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Loading…</p>
            )}
          </Card>
        </div>

        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">System</h3>
          {health.isLoading && <p className="mt-3 text-sm text-slate-500">Checking…</p>}
          {health.data && (
            <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
              <dt className="text-slate-500">Status</dt>
              <dd>
                <StateChip state={health.data.status} />
              </dd>
              <dt className="text-slate-500">Database</dt>
              <dd>
                <StateChip state={health.data.db} />
              </dd>
              <dt className="text-slate-500">Redis</dt>
              <dd>
                <StateChip state={health.data.redis} />
              </dd>
              <dt className="text-slate-500">Controllers</dt>
              <dd className="font-mono">{controllers.data?.count ?? "…"}</dd>
              <dt className="text-slate-500">Version</dt>
              <dd className="font-mono">{health.data.version}</dd>
            </dl>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <Card className="p-0 overflow-hidden">
          <div className="flex items-baseline justify-between gap-2 border-b border-slate-800 px-4 py-3">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Active fleets
            </h3>
            <Link to="/fleets" search={{ blueprint: undefined }} className="text-xs text-indigo-400 hover:text-indigo-300">
              All fleets →
            </Link>
          </div>
          {fleets.isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
          {fleets.data && activeFleets.length === 0 && (
            <EmptyState title="No active fleets" hint="Ramp a fleet to see it here." />
          )}
          {activeFleets.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <th className="px-4 py-2 text-left font-medium">State</th>
                  <th className="px-4 py-2 text-right font-medium">Devices</th>
                  <th className="px-4 py-2 text-right font-medium">Ready</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {activeFleets.slice(0, 6).map((f) => {
                  const ready = Object.entries(f.device_states ?? {})
                    .filter(([s]) => READY_STATES.has(s))
                    .reduce((a, [, n]) => a + n, 0);
                  return (
                    <tr key={f.id} className="hover:bg-slate-900/40">
                      <td className="px-4 py-2">
                        <Link
                          to="/fleets/$id"
                          params={{ id: f.id }}
                          className="text-slate-200 hover:text-white"
                        >
                          {f.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2">
                        <StateChip state={f.state} />
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-xs">{f.device_count}</td>
                      <td className="px-4 py-2 text-right font-mono text-xs text-slate-400">
                        {ready}/{f.device_count}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="p-0 overflow-hidden">
          <div className="border-b border-slate-800 px-4 py-3">
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Recent activity
            </h3>
          </div>
          {audit.isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
          {audit.isError && (
            <p className="p-4 text-sm text-slate-500">
              Audit log visible to administrators only.
            </p>
          )}
          {audit.data && audit.data.results.length === 0 && (
            <EmptyState
              title="No audit entries yet"
              hint="Create or modify a resource to see it appear here."
            />
          )}
          {audit.data && audit.data.results.length > 0 && (
            <ul className="divide-y divide-slate-800">
              {audit.data.results.slice(0, 6).map((a) => (
                <li key={a.id} className="flex items-center justify-between px-4 py-3 text-sm">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-300">
                      {a.action}
                    </span>
                    <span className="truncate text-slate-400">
                      {a.target_type}
                      {a.target_id ? ` · ${a.target_id.slice(0, 8)}` : ""}
                    </span>
                  </div>
                  <span className="whitespace-nowrap font-mono text-xs text-slate-500">
                    {humanRelative(a.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <section className="mt-6">
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Device state breakdown
          </h3>
          {devices.isLoading && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
          {devices.data && devicesTotal === 0 && (
            <p className="mt-3 text-sm text-slate-500">
              No devices provisioned — create a fleet to start populating the engine.
            </p>
          )}
          {devicesTotal > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {Object.entries(devicesByState).map(([state, count]) => (
                <li key={state} className="flex items-center gap-2 text-sm">
                  <StateChip state={state} />
                  <span className="font-mono text-slate-300">× {count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </>
  );
}
