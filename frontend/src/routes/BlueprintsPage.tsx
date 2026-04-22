import { Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";

export function BlueprintsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["blueprints"], queryFn: endpoints.blueprints.list });

  return (
    <>
      <PageHeader
        title="Blueprints"
        subtitle="YAML-authored site descriptions that materialise into fleets."
        actions={
          <Link
            to="/blueprints/new"
            className="inline-flex h-10 items-center justify-center rounded-md bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500"
          >
            New blueprint
          </Link>
        }
      />

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No blueprints yet"
          hint="Author a YAML blueprint; the validator runs JSON Schema + semantic checks (hostname uniqueness, uplink resolution)."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Version</th>
                <th className="px-4 py-2 text-left font-medium">Active</th>
                <th className="px-4 py-2 text-left font-medium">Updated</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((bp) => (
                <tr key={bp.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-medium">
                    <Link to="/blueprints/$id" params={{ id: bp.id }} className="hover:text-white">
                      {bp.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">v{bp.version}</td>
                  <td className="px-4 py-3 text-slate-400">{bp.is_active ? "yes" : "no"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {new Date(bp.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to="/blueprints/$id"
                      params={{ id: bp.id }}
                      className="text-sm text-indigo-400 hover:text-indigo-300"
                    >
                      Edit →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <div className="mt-6 text-xs text-slate-500">
        Refetched automatically after{" "}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => qc.invalidateQueries({ queryKey: ["blueprints"] })}
        >
          Refresh
        </Button>
      </div>
    </>
  );
}
