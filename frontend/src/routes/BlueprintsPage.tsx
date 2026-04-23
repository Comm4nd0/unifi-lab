import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints, type Blueprint } from "../api/client";
import { Button, Card, EmptyState, Input, Label, PageHeader, Select } from "../components/ui";

type SortKey = "updated_at" | "name" | "version";

export function BlueprintsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["blueprints"], queryFn: endpoints.blueprints.list });

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("updated_at");

  const rows = list.data?.results ?? [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matched = q
      ? rows.filter((bp) => {
          const desc = (bp.parsed_json as { description?: string })?.description ?? "";
          const hay = `${bp.name} ${desc}`.toLowerCase();
          return hay.includes(q);
        })
      : rows.slice();
    const sorter: Record<SortKey, (a: Blueprint, b: Blueprint) => number> = {
      updated_at: (a, b) => b.updated_at.localeCompare(a.updated_at),
      name: (a, b) => a.name.localeCompare(b.name),
      version: (a, b) => b.version - a.version,
    };
    return matched.sort(sorter[sortKey]);
  }, [rows, search, sortKey]);

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
      {list.data && rows.length === 0 && (
        <EmptyState
          title="No blueprints yet"
          hint="Author a YAML blueprint; the validator runs JSON Schema + semantic checks (hostname uniqueness, uplink resolution)."
        />
      )}
      {list.data && rows.length > 0 && (
        <>
          <Card className="mb-4">
            <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
              <div>
                <Label>Search</Label>
                <Input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Name or description…"
                />
              </div>
              <div>
                <Label>Sort</Label>
                <Select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
                  <option value="updated_at">Recently updated</option>
                  <option value="name">Name (A → Z)</option>
                  <option value="version">Version (high → low)</option>
                </Select>
              </div>
              <div>
                <Label>&nbsp;</Label>
                <Button variant="ghost" onClick={() => setSearch("")} disabled={!search}>
                  Clear
                </Button>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Showing {filtered.length.toLocaleString()} of {rows.length.toLocaleString()}{" "}
              blueprints.
            </p>
          </Card>

          <Card className="p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <th className="px-4 py-2 text-left font-medium">Version</th>
                  <th className="px-4 py-2 text-left font-medium">Devices</th>
                  <th className="px-4 py-2 text-left font-medium">Active</th>
                  <th className="px-4 py-2 text-left font-medium">Updated</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map((bp) => {
                  const deviceCount = Array.isArray(
                    (bp.parsed_json as { site?: { devices?: unknown[] } })?.site?.devices,
                  )
                    ? (bp.parsed_json as { site: { devices: unknown[] } }).site.devices.length
                    : 0;
                  return (
                    <tr key={bp.id} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-medium">
                        <Link
                          to="/blueprints/$id"
                          params={{ id: bp.id }}
                          className="hover:text-white"
                        >
                          {bp.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">v{bp.version}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{deviceCount}</td>
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
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-sm text-slate-500">
                      No blueprints match "{search}".{" "}
                      <button
                        type="button"
                        onClick={() => setSearch("")}
                        className="text-indigo-400 hover:text-indigo-300"
                      >
                        Clear
                      </button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
        </>
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
