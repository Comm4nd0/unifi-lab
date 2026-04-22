import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { Button, Card, PageHeader, StateChip } from "../components/ui";

export function ControllerDetailPage() {
  const { id } = useParams({ from: "/_app/controllers/$id" });
  const navigate = useNavigate();
  const qc = useQueryClient();

  const ctrl = useQuery({
    queryKey: ["controllers", id],
    queryFn: () => endpoints.controllers.get(id),
  });

  const devices = useQuery({ queryKey: ["devices"], queryFn: endpoints.devices.list });
  const related = devices.data?.results.filter((d) => d.controller_target === id) ?? [];

  const del = useMutation({
    mutationFn: () => endpoints.controllers.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["controllers"] });
      navigate({ to: "/controllers" });
    },
  });

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

      <section className="mt-6">
        <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-400">
          Devices on this controller
        </h3>
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
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                  <th className="px-4 py-2 text-left font-medium">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {related.map((d) => (
                  <tr key={d.id}>
                    <td className="px-4 py-2 font-mono text-xs">
                      <Link
                        to="/devices/$id"
                        params={{ id: d.id }}
                        className="hover:text-white"
                      >
                        {d.mac_address}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{d.model_code}</td>
                    <td className="px-4 py-2">
                      <StateChip state={d.state} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
