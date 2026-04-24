import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";

import { endpoints, type InformExchange } from "../api/client";
import { useChannel } from "../api/ws";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

const TYPE_TONE: Record<string, string> = {
  adopt: "bg-indigo-900/40 text-indigo-300 border-indigo-800",
  heartbeat: "bg-emerald-900/40 text-emerald-200 border-emerald-800",
  config_push: "bg-sky-900/40 text-sky-200 border-sky-800",
  stats: "bg-slate-900 text-slate-300 border-slate-700",
  error: "bg-rose-900/40 text-rose-200 border-rose-800",
};

function humanRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const delta = Date.now() - new Date(iso).getTime();
  if (delta < 0) return "just now";
  if (delta < 60_000) return `${Math.max(1, Math.round(delta / 1000))}s ago`;
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
  if (delta < 86_400_000) return `${Math.round(delta / 3_600_000)}h ago`;
  return `${Math.round(delta / 86_400_000)}d ago`;
}

function payloadSize(p: Record<string, unknown> | null | undefined): number {
  if (!p) return 0;
  try {
    return JSON.stringify(p).length;
  } catch {
    return 0;
  }
}

function humanBytes(n: number): string {
  if (n === 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function InformInspectorPage() {
  const { id } = useParams({ from: "/_app/devices/$id/inform" });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [liveRows, setLiveRows] = useState<InformExchange[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  const device = useQuery({
    queryKey: ["devices", id],
    queryFn: () => endpoints.devices.get(id),
  });

  // Historical log via the cursor endpoint. ``next`` is a full URL we
  // pass straight back on the next page — see ``endpoints.devices.informLog``.
  const history = useInfiniteQuery({
    queryKey: ["devices", id, "inform-log"],
    queryFn: ({ pageParam }: { pageParam: string | undefined }) =>
      endpoints.devices.informLog(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
  });

  // WebSocket live tail — the consumer sends full ``inform.exchange``
  // envelopes with the serialized row as ``data``, so we can prepend
  // straight into the list and dedupe against the historical page by id.
  const { state: wsState, messages } = useChannel({ path: `/ws/devices/${id}/inform/` });

  useEffect(() => {
    const fresh: InformExchange[] = [];
    for (const m of messages) {
      if (m.type !== "inform.exchange") continue;
      const data = m.data as InformExchange & { id?: string };
      if (!data || typeof data.id !== "string") continue;
      fresh.push(data);
    }
    // Keep only rows that aren't already in the historical first page.
    setLiveRows(fresh);
  }, [messages]);

  const force = useMutation({
    mutationFn: () => endpoints.devices.forceInform(id),
  });

  const historyRows = history.data?.pages.flatMap((p) => p.results) ?? [];

  // Merge live + history, dedupe by id, newest first.
  const rows = useMemo(() => {
    const seen = new Set<string>();
    const out: InformExchange[] = [];
    const pushMaybe = (row: InformExchange) => {
      if (!row.id || seen.has(row.id)) return;
      seen.add(row.id);
      out.push(row);
    };
    // liveRows come in WS arrival order (oldest → newest as received).
    // Reverse so newest lands first, matching the history ordering.
    for (const r of [...liveRows].reverse()) pushMaybe(r);
    for (const r of historyRows) pushMaybe(r);
    return out;
  }, [liveRows, historyRows]);

  const toggle = (rowId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rowId)) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  };

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      // clipboard blocked — user can still select manually
    }
  };

  return (
    <>
      <PageHeader
        title="Inform Inspector"
        subtitle={
          device.data
            ? `${device.data.mac_address} · ${device.data.model_code}${
                device.data.hostname ? ` · ${device.data.hostname}` : ""
              }`
            : "Loading device…"
        }
        actions={
          <>
            <Link
              to="/devices/$id"
              params={{ id }}
              className="text-sm text-slate-400 hover:text-white"
            >
              ← Device detail
            </Link>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => force.mutate()}
              disabled={force.isPending}
            >
              {force.isPending ? "Forcing…" : "Force inform"}
            </Button>
          </>
        }
      />

      <div className="mb-4 flex items-center gap-3 text-xs text-slate-500">
        <span>Live:</span>
        <StateChip state={wsState} />
        <span className="text-slate-700">·</span>
        <span>
          {rows.length} exchange{rows.length === 1 ? "" : "s"} loaded
          {liveRows.length > 0 && (
            <span className="ml-1 text-emerald-400">
              ({liveRows.length} live)
            </span>
          )}
        </span>
      </div>

      {history.isLoading && !history.data && (
        <p className="text-sm text-slate-500">Loading inform log…</p>
      )}
      {history.data && rows.length === 0 && (
        <EmptyState
          title="No inform exchanges yet"
          hint="Trigger one with Force inform, or wait for the worker's next heartbeat tick."
        />
      )}

      {rows.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">When</th>
                <th className="px-4 py-2 text-left font-medium">Type</th>
                <th className="px-4 py-2 text-left font-medium">Direction</th>
                <th className="px-4 py-2 text-right font-medium">Size</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rows.map((r) => {
                const isExpanded = expanded.has(r.id);
                const typeClass =
                  TYPE_TONE[r.exchange_type] ?? TYPE_TONE.stats;
                const hasIn = !!r.payload_in;
                const hasOut = !!r.payload_out;
                const totalSize =
                  payloadSize(r.payload_in) + payloadSize(r.payload_out);
                return (
                  <ExchangeRow
                    key={r.id}
                    row={r}
                    isExpanded={isExpanded}
                    typeClass={typeClass}
                    hasIn={hasIn}
                    hasOut={hasOut}
                    totalSize={totalSize}
                    copiedKey={copied}
                    onToggle={() => toggle(r.id)}
                    onCopy={copy}
                  />
                );
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-slate-800 px-4 py-3 text-xs text-slate-500">
            <span>
              Showing {rows.length.toLocaleString()} exchange
              {rows.length === 1 ? "" : "s"} (newest first).
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => history.fetchNextPage()}
              disabled={!history.hasNextPage || history.isFetchingNextPage}
            >
              {history.isFetchingNextPage
                ? "Loading…"
                : history.hasNextPage
                  ? "Load older →"
                  : "End of log"}
            </Button>
          </div>
        </Card>
      )}
    </>
  );
}

function ExchangeRow({
  row,
  isExpanded,
  typeClass,
  hasIn,
  hasOut,
  totalSize,
  copiedKey,
  onToggle,
  onCopy,
}: {
  row: InformExchange;
  isExpanded: boolean;
  typeClass: string;
  hasIn: boolean;
  hasOut: boolean;
  totalSize: number;
  copiedKey: string | null;
  onToggle: () => void;
  onCopy: (key: string, text: string) => void;
}) {
  const inJson = hasIn ? JSON.stringify(row.payload_in, null, 2) : "";
  const outJson = hasOut ? JSON.stringify(row.payload_out, null, 2) : "";

  return (
    <>
      <tr className="hover:bg-slate-900/40">
        <td className="px-4 py-2 align-top font-mono text-xs">
          <div className="text-slate-300">{humanRelative(row.exchanged_at)}</div>
          <div className="text-[10px] text-slate-600">
            {row.exchanged_at ? new Date(row.exchanged_at).toLocaleString() : "—"}
          </div>
        </td>
        <td className="px-4 py-2 align-top">
          <span
            className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase ${typeClass}`}
          >
            {row.exchange_type}
          </span>
        </td>
        <td className="px-4 py-2 align-top font-mono text-[11px] text-slate-400">
          {hasIn && <span title="device → controller">▲ in</span>}
          {hasIn && hasOut && <span className="mx-1 text-slate-600">·</span>}
          {hasOut && <span title="controller → device">▼ out</span>}
          {!hasIn && !hasOut && <span className="text-slate-600">—</span>}
        </td>
        <td className="px-4 py-2 text-right align-top font-mono text-xs text-slate-500">
          {humanBytes(totalSize)}
        </td>
        <td className="px-4 py-2 text-right align-top">
          <button
            type="button"
            onClick={onToggle}
            className="text-xs text-indigo-400 hover:text-indigo-300"
          >
            {isExpanded ? "Hide" : "Details"}
          </button>
        </td>
      </tr>
      {isExpanded && (
        <tr className="bg-slate-950">
          <td colSpan={5} className="px-4 py-3">
            <div className="grid gap-3 md:grid-cols-2">
              <PayloadBlock
                label="payload_in"
                content={inJson || "null"}
                hint="device → controller"
                copyKey={`${row.id}-in`}
                copiedKey={copiedKey}
                onCopy={onCopy}
              />
              <PayloadBlock
                label="payload_out"
                content={outJson || "null"}
                hint="controller → device"
                copyKey={`${row.id}-out`}
                copiedKey={copiedKey}
                onCopy={onCopy}
              />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function PayloadBlock({
  label,
  content,
  hint,
  copyKey,
  copiedKey,
  onCopy,
}: {
  label: string;
  content: string;
  hint: string;
  copyKey: string;
  copiedKey: string | null;
  onCopy: (key: string, text: string) => void;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-wide text-slate-500">
          {label} <span className="ml-1 text-slate-600">· {hint}</span>
        </p>
        <button
          type="button"
          onClick={() => onCopy(copyKey, content)}
          className="text-[10px] text-slate-500 hover:text-slate-300"
          disabled={content === "null"}
        >
          {copiedKey === copyKey ? "Copied ✓" : "Copy"}
        </button>
      </div>
      <pre className="mt-1 max-h-80 overflow-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[11px] text-slate-300">
        {content}
      </pre>
    </div>
  );
}
