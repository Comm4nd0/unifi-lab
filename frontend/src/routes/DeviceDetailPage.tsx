import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

export function DeviceDetailPage() {
  const { id } = useParams({ from: "/_app/devices/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const device = useQuery({ queryKey: ["devices", id], queryFn: () => endpoints.devices.get(id) });

  const del = useMutation({
    mutationFn: () => endpoints.devices.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      navigate({ to: "/devices" });
    },
  });

  if (device.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (device.error) return <p className="text-sm text-red-400">{(device.error as Error).message}</p>;
  if (!device.data) return null;

  const d = device.data;

  return (
    <>
      <PageHeader
        title={d.mac_address}
        subtitle={`${d.model_code} · ${d.firmware_version || "unversioned"}`}
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
              onClick={() => {
                if (confirm(`Delete device ${d.mac_address}?`)) del.mutate();
              }}
              disabled={del.isPending}
            >
              Delete
            </Button>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Identity</h3>
          <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
            <dt className="text-slate-500">MAC</dt>
            <dd className="font-mono text-xs">{d.mac_address}</dd>
            <dt className="text-slate-500">Serial</dt>
            <dd className="font-mono text-xs">{d.serial_number}</dd>
            <dt className="text-slate-500">Model</dt>
            <dd>{d.model_code}</dd>
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
            <dd>{d.fleet ?? <span className="text-slate-600">none</span>}</dd>
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

      <section className="mt-6">
        <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-400">
          Inform exchanges
        </h3>
        <EmptyState
          title="No exchanges yet"
          hint="Open the Inform Inspector to tail live traffic once the engine starts generating it."
        />
      </section>
    </>
  );
}
