import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { useChannel } from "../api/ws";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

type DirFilter = "" | "outbound" | "inbound";

export function InformInspectorPage() {
  const { id } = useParams({ from: "/_app/devices/$id/inform" });
  const [paused, setPaused] = useState(false);
  const [dirFilter, setDirFilter] = useState<DirFilter>("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const device = useQuery({ queryKey: ["devices", id], queryFn: () => endpoints.devices.get(id) });

  const { state, messages, clear } = useChannel({
    path: paused ? "" : `/ws/devices/${id}/inform/`,
  });

  const force = useMutation({
    mutationFn: () => endpoints.devices.forceInform(id),
  });

  const rows = useMemo(() => {
    let r = messages.filter((m) => m.type !== "connection.ready");
    if (dirFilter === "outbound") {
      r = r.filter(
        (m) =>
          (m.data?.direction as string) === "outbound" ||
          m.type?.includes("request"),
      );
    } else if (dirFilter === "inbound") {
      r = r.filter(
        (m) =>
          (m.data?.direction as string) === "inbound" ||
          m.type?.includes("response"),
      );
    }
    return r;
  }, [messages, dirFilter]);

  // Clamp selected index when rows shrink.
  useEffect(() => {
    setSelectedIdx((i) => Math.min(i, Math.max(0, rows.length - 1)));
  }, [rows.length]);

  // j/k keyboard navigation + Enter/Space to expand.
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const selectedIdxRef = useRef(selectedIdx);
  selectedIdxRef.current = selectedIdx;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      )
        return;
      if (e.key === "j") {
        setSelectedIdx((i) => Math.min(rowsRef.current.length - 1, i + 1));
        e.preventDefault();
      } else if (e.key === "k") {
        setSelectedIdx((i) => Math.max(0, i - 1));
        e.preventDefault();
      } else if (e.key === "Enter" || e.key === " ") {
        const row = rowsRef.current[selectedIdxRef.current];
        if (!row) return;
        const rid = rowId(row, selectedIdxRef.current);
        setExpandedIds((s) => {
          const next = new Set(s);
          if (next.has(rid)) next.delete(rid);
          else next.add(rid);
          return next;
        });
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleExpand = (rid: string) => {
    setExpandedIds((s) => {
      const next = new Set(s);
      if (next.has(rid)) next.delete(rid);
      else next.add(rid);
      return next;
    });
  };

  const allExpanded = rows.length > 0 && rows.every((r, i) => expandedIds.has(rowId(r, i)));
  const toggleExpandAll = () => {
    if (allExpanded) {
      setExpandedIds(new Set());
    } else {
      setExpandedIds(new Set(rows.map((r, i) => rowId(r, i))));
    }
  };

  const copyPayload = async (data: unknown) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    } catch {
      // clipboard blocked
    }
  };

  return (
    <>
      <PageHeader
        title="Inform Inspector"
        subtitle={
          device.data
            ? `${device.data.mac_address} · ${device.data.model_code}`
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
              Force inform
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setPaused((p) => !p)}>
              {paused ? "Resume" : "Pause"}
            </Button>
            <Button size="sm" variant="ghost" onClick={clear}>
              Clear
            </Button>
          </>
        }
      />

      {/* Status + filter bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span className="flex items-center gap-2 text-sm text-slate-400">
          <span>WebSocket:</span>
          <StateChip state={state} />
        </span>
        <span className="text-slate-700">·</span>
        <span className="text-sm text-slate-400">
          {rows.length} message{rows.length === 1 ? "" : "s"}
        </span>

        {/* Direction filter */}
        <div className="ml-auto flex overflow-hidden rounded-md border border-slate-800 bg-slate-900 text-xs">
          {(
            [
              { v: "" as DirFilter, label: "All" },
              { v: "outbound" as DirFilter, label: "↑ Outbound" },
              { v: "inbound" as DirFilter, label: "↓ Inbound" },
            ] as const
          ).map(({ v, label }) => (
            <button
              key={v}
              type="button"
              onClick={() => setDirFilter(v)}
              className={
                "px-3 py-1.5 transition " +
                (dirFilter === v
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-slate-200")
              }
            >
              {label}
            </button>
          ))}
        </div>

        {rows.length > 0 && (
          <button
            type="button"
            onClick={toggleExpandAll}
            className="text-xs text-slate-400 hover:text-white"
          >
            {allExpanded ? "Collapse all" : "Expand all"}
          </button>
        )}
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No exchanges yet"
          hint="Inform protocol codec is stubbed. Once the engine starts generating real traffic, it will stream here live."
        />
      ) : (
        <Card className="p-0 overflow-hidden">
          <ul className="divide-y divide-slate-800">
            {rows.map((m, i) => {
              const rid = rowId(m, i);
              const expanded = expandedIds.has(rid);
              const isSelected = i === selectedIdx;
              const dir = (m.data?.direction as string) ?? (m.type?.includes("request") ? "outbound" : m.type?.includes("response") ? "inbound" : "");
              return (
                <li
                  key={rid}
                  className={
                    "font-mono text-xs transition-colors " +
                    (isSelected ? "bg-indigo-950/40 ring-1 ring-inset ring-indigo-800" : "hover:bg-slate-900/40")
                  }
                  onClick={() => {
                    setSelectedIdx(i);
                    toggleExpand(rid);
                  }}
                >
                  <div className="flex cursor-pointer items-center gap-3 px-4 py-3 select-none">
                    <span className="w-6 text-slate-600">#{m.seq ?? "?"}</span>
                    <span className="text-slate-500">{m.ts}</span>
                    <span className="rounded bg-indigo-900/40 px-2 py-0.5 text-indigo-300">
                      {m.type}
                    </span>
                    {dir === "outbound" && (
                      <span className="text-emerald-400" title="Device → Controller">↑</span>
                    )}
                    {dir === "inbound" && (
                      <span className="text-amber-400" title="Controller → Device">↓</span>
                    )}
                    <span className="ml-auto text-slate-600">{expanded ? "▲" : "▼"}</span>
                  </div>
                  {expanded && (
                    <div className="px-4 pb-3">
                      <div className="flex items-center justify-end gap-2 pb-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyPayload(m.data);
                          }}
                          className="text-[10px] text-slate-500 hover:text-slate-300"
                        >
                          Copy JSON
                        </button>
                      </div>
                      <pre className="overflow-x-auto rounded bg-slate-950 p-3 text-[11px] text-slate-300">
                        {JSON.stringify(m.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <p className="mt-4 text-xs text-slate-600">
        <kbd className="rounded bg-slate-800 px-1 font-mono">j</kbd>/
        <kbd className="rounded bg-slate-800 px-1 font-mono">k</kbd> navigate ·{" "}
        <kbd className="rounded bg-slate-800 px-1 font-mono">Enter</kbd> expand/collapse
      </p>
    </>
  );
}

function rowId(m: { seq?: number }, i: number): string {
  return m.seq != null ? `seq-${m.seq}` : `idx-${i}`;
}
