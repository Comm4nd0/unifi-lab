import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { HealthCheckModal } from "../components/HealthCheckModal";
import { Button, Card, EmptyState, PageHeader, Select, StateChip } from "../components/ui";

const READY_STATES = new Set(["adopted", "heartbeat"]);

export function ControllerDetailPage() {
  const { id } = useParams({ from: "/_app/controllers/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const ctrl = useQuery({
    queryKey: ["controllers", id],
    queryFn: () => endpoints.controllers.get(id),
    refetchInterval: 30_000,
  });

  const devices = useQuery({
    queryKey: ["devices"],
    queryFn: endpoints.devices.list,
    refetchInterval: 15_000,
  });
  const fleets = useQuery({
    queryKey: ["fleets"],
    queryFn: endpoints.fleets.list,
    refetchInterval: 15_000,
  });

  const related = devices.data?.results.filter((d) => d.controller_target === id) ?? [];
  const relatedFleets = fleets.data?.results.filter((f) => f.controller_target === id) ?? [];

  const stateCounts = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const d of related) {
      acc[d.state] = (acc[d.state] ?? 0) + 1;
    }
    return acc;
  }, [related]);

  const readyCount = Object.entries(stateCounts)
    .filter(([s]) => READY_STATES.has(s))
    .reduce((a, [, n]) => a + n, 0);
  const adoptionPct = related.length > 0 ? Math.round((readyCount / related.length) * 100) : 0;

  const [stateFilter, setStateFilter] = useState<string>("");
  const filteredDevices = stateFilter
    ? related.filter((d) => d.state === stateFilter)
    : related;

  const del = useMutation({
    mutationFn: () => endpoints.controllers.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["controllers"] });
      navigate({ to: "/controllers" });
    },
  });

  const [healthModalOpen, setHealthModalOpen] = useState(false);

  if (ctrl.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (ctrl.error) return <p className="text-sm text-red-400">{(ctrl.error as Error).message}</p>;
  if (!ctrl.data) return null;

  const c = ctrl.data;

  return (
    <>
      <PageHeader
        title={c.name}
        subtitle={`Controller · ${c.kind}`}
        actions={
          <>
            <Link to="/controllers" className="text-sm text-slate-400 hover:text-white">
              ← All controllers
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setHealthModalOpen(true)}
              title="Probe controller reachability + API credentials"
            >
              Check health
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                if (confirm(`Delete ${c.name}?`)) del.mutate();
              }}
              disabled={del.isPending}
            >
              Delete
            </Button>
          </>
        }
      />

      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <Kpi label="Devices" value={related.length} />
        <Kpi
          label="Adopted"
          value={readyCount}
          sub={related.length ? `${adoptionPct}%` : "—"}
          tone={readyCount > 0 && readyCount === related.length ? "good" : "default"}
        />
        <Kpi label="Fleets" value={relatedFleets.length} />
        <Kpi
          label="Health"
          value={c.health || "—"}
          sub={c.is_active ? "active" : "disabled"}
          tone={c.health === "ok" ? "good" : c.health === "degraded" ? "warn" : "default"}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Identity</h3>
          <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-y-2 text-sm">
            <dt className="text-slate-500">Name</dt>
            <dd>{c.name}</dd>
            <dt className="text-slate-500">Kind</dt>
            <dd className="font-mono text-xs">{c.kind}</dd>
            <dt className="text-slate-500">Health</dt>
            <dd>
              <StateChip state={c.health} />
            </dd>
            <dt className="text-slate-500">Verify TLS</dt>
            <dd>{c.verify_tls ? "yes" : "no"}</dd>
            <dt className="text-slate-500">Active</dt>
            <dd>{c.is_active ? "yes" : "no"}</dd>
            <dt className="text-slate-500">Created</dt>
            <dd className="font-mono text-xs text-slate-400">
              {new Date(c.created_at).toLocaleString()}
            </dd>
          </dl>
        </Card>

        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Endpoints</h3>
          <dl className="mt-3 grid grid-cols-[5.5rem_1fr] gap-y-2 text-sm">
            <dt className="text-slate-500">Inform</dt>
            <dd className="font-mono text-xs break-all">{c.inform_url}</dd>
            <dt className="text-slate-500">API</dt>
            <dd className="font-mono text-xs break-all">{c.api_url}</dd>
          </dl>
          <p className="mt-4 text-xs text-slate-500">
            API credentials are write-only; decrypt-and-display is out of scope for v1.
          </p>
        </Card>
      </div>

      {related.length > 0 && (
        <Card className="mt-6">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Device state breakdown
          </h3>
          <ul className="mt-3 flex flex-wrap gap-2">
            {Object.entries(stateCounts)
              .sort((a, b) => b[1] - a[1])
              .map(([state, count]) => (
                <li key={state} className="flex items-center gap-2 text-sm">
                  <StateChip state={state} />
                  <span className="font-mono text-slate-300">× {count}</span>
                </li>
              ))}
          </ul>
        </Card>
      )}

      <section className="mt-6">
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Fleets on this controller
          </h3>
          <Link to="/fleets" search={{ blueprint: undefined }} className="text-xs text-indigo-400 hover:text-indigo-300">
            All fleets →
          </Link>
        </div>
        {relatedFleets.length === 0 ? (
          <EmptyState
            title="No fleets on this controller"
            hint="Create one from Fleets → New fleet and pick this controller."
          />
        ) : (
          <Card className="p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <th className="px-4 py-2 text-left font-medium">State</th>
                  <th className="px-4 py-2 text-right font-medium">Devices</th>
                  <th className="px-4 py-2 text-right font-medium">Ready</th>
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {relatedFleets.map((f) => {
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
                      <td className="px-4 py-2 font-mono text-xs text-slate-400">{f.model_code}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Devices on this controller
          </h3>
          {related.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>State:</span>
              <Select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="w-auto"
              >
                <option value="">All</option>
                {Object.keys(stateCounts)
                  .sort()
                  .map((s) => (
                    <option key={s} value={s}>
                      {s} ({stateCounts[s]})
                    </option>
                  ))}
              </Select>
            </div>
          )}
        </div>
        {related.length === 0 ? (
          <Card>
            <p className="text-sm text-slate-400">
              No devices yet.{" "}
              <Link to="/devices" className="text-indigo-400 underline">
                Create one →
              </Link>
            </p>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">MAC</th>
                  <th className="px-4 py-2 text-left font-medium">Hostname</th>
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                  <th className="px-4 py-2 text-left font-medium">State</th>
                  <th className="px-4 py-2 text-left font-medium">Last heartbeat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredDevices.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-2 font-mono text-xs">
                      <Link
                        to="/devices/$id"
                        params={{ id: d.id }}
                        className="hover:text-white"
                      >
                        {d.mac_address}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-300">
                      {d.hostname || <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">{d.model_code}</td>
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
                {filteredDevices.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-500">
                      No devices match the state filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <HealthCheckModal
        controllerId={id}
        open={healthModalOpen}
        onClose={() => setHealthModalOpen(false)}
      />
    </>
  );
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
          "mt-2 text-2xl font-semibold " +
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
