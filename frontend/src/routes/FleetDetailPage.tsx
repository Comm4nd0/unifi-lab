import { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { TopologyGraph } from "../components/TopologyGraph";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

type Tab = "overview" | "topology" | "devices";

export function FleetDetailPage() {
  const { id } = useParams({ from: "/_app/fleets/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [tab, setTab] = useState<Tab>("overview");

  const fleet = useQuery({
    queryKey: ["fleets", id],
    queryFn: () => endpoints.fleets.get(id),
    refetchInterval: 5_000,
  });
  const devices = useQuery({ queryKey: ["devices"], queryFn: endpoints.devices.list });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });

  // Fetch the blueprint only when the fleet has one — topology uses uplinks.
  const blueprint = useQuery({
    queryKey: ["blueprints", fleet.data?.blueprint],
    queryFn: () => endpoints.blueprints.get(fleet.data!.blueprint!),
    enabled: !!fleet.data?.blueprint,
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
      navigate({ to: "/fleets" });
    },
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

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "topology", label: "Topology" },
    { id: "devices", label: `Devices (${related.length})` },
  ];

  return (
    <>
      <PageHeader
        title={f.name}
        subtitle={`${f.device_count} × ${f.model_code}`}
        actions={
          <>
            <Link to="/fleets" className="text-sm text-slate-400 hover:text-white">
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
              onClick={() => {
                if (confirm(`Tear down ${f.name}? Devices will be despawned.`)) tear.mutate();
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
        </div>
      )}

      {tab === "topology" && (
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Topology
          </h3>
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
    </>
  );
}
