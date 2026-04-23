import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { Button, Card, EmptyState, Input, Label, PageHeader, Select } from "../components/ui";

function humanRelative(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  if (delta < 60_000) return "just now";
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
  if (delta < 86_400_000) return `${Math.round(delta / 3_600_000)}h ago`;
  return `${Math.round(delta / 86_400_000)}d ago`;
}

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const list = useQuery({
    queryKey: ["audit", { page, action: actionFilter, target_type: targetFilter }],
    queryFn: () =>
      endpoints.audit.list({
        page,
        action: actionFilter || undefined,
        target_type: targetFilter || undefined,
      }),
  });

  // Actions + target_types for the filter selects — pulled from the
  // visible page so we don't need a separate distinct-values endpoint.
  // Good enough for the 25-row window; if the list grows we can promote
  // this to the backend.
  const { actions, targets } = useMemo(() => {
    const a = new Set<string>();
    const t = new Set<string>();
    for (const row of list.data?.results ?? []) {
      if (row.action) a.add(row.action);
      if (row.target_type) t.add(row.target_type);
    }
    return {
      actions: Array.from(a).sort(),
      targets: Array.from(t).sort(),
    };
  }, [list.data]);

  const total = list.data?.count ?? 0;
  const hasPrev = page > 1;
  const hasNext = (list.data?.next ?? null) != null;

  const toggle = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle="Every security-relevant action. Admin-only — shared with tenants as needed for compliance."
      />

      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto_auto]">
          <div>
            <Label>Action</Label>
            <Select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All actions</option>
              {actions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Target type</Label>
            <Select
              value={targetFilter}
              onChange={(e) => {
                setTargetFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All types</option>
              {targets.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>&nbsp;</Label>
            <Button
              variant="ghost"
              onClick={() => {
                setActionFilter("");
                setTargetFilter("");
                setPage(1);
              }}
              disabled={!actionFilter && !targetFilter}
            >
              Clear filters
            </Button>
          </div>
          <div>
            <Label>Page</Label>
            <Input
              type="number"
              min={1}
              value={page}
              onChange={(e) => setPage(Math.max(1, Number(e.target.value) || 1))}
              className="w-20"
            />
          </div>
        </div>
      </Card>

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.isError && (
        <p className="text-sm text-slate-500">
          Audit log is visible to administrators only.
        </p>
      )}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No audit entries"
          hint={
            actionFilter || targetFilter
              ? "Try clearing the filters above."
              : "Create or modify a resource to see entries here."
          }
        />
      )}

      {list.data && list.data.results.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">When</th>
                <th className="px-4 py-2 text-left font-medium">Actor</th>
                <th className="px-4 py-2 text-left font-medium">Action</th>
                <th className="px-4 py-2 text-left font-medium">Target</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((row) => {
                const isExpanded = !!expanded[row.id];
                const detail = JSON.stringify(
                  { diff: row.diff, metadata: row.metadata },
                  null,
                  2,
                );
                return (
                  <Fragment key={row.id}>
                    <tr className="hover:bg-slate-900/40">
                      <td className="px-4 py-2 align-top font-mono text-xs text-slate-500">
                        <div>{humanRelative(row.created_at)}</div>
                        <div className="text-[10px] text-slate-600">
                          {new Date(row.created_at).toLocaleString()}
                        </div>
                      </td>
                      <td className="px-4 py-2 align-top font-mono text-xs text-slate-400">
                        {row.actor ?? <span className="text-slate-600">system</span>}
                      </td>
                      <td className="px-4 py-2 align-top">
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-300">
                          {row.action}
                        </span>
                      </td>
                      <td className="px-4 py-2 align-top font-mono text-xs text-slate-400">
                        {row.target_type || <span className="text-slate-600">—</span>}
                        {row.target_id && (
                          <span className="text-slate-600"> · {row.target_id.slice(0, 10)}</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right align-top">
                        <button
                          type="button"
                          onClick={() => toggle(row.id)}
                          className="text-xs text-indigo-400 hover:text-indigo-300"
                        >
                          {isExpanded ? "Hide" : "Details"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-950">
                        <td colSpan={5} className="px-4 py-3">
                          <pre className="overflow-auto whitespace-pre-wrap text-[11px] text-slate-400">
                            {detail}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>

          <div className="flex items-center justify-between border-t border-slate-800 px-4 py-2 text-xs text-slate-500">
            <span>
              Page {page} · {total.toLocaleString()} total entries
            </span>
            <span className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                disabled={!hasPrev}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ← Prev
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={!hasNext}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </Button>
            </span>
          </div>
        </Card>
      )}
    </>
  );
}
