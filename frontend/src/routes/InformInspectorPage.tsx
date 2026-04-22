import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { useChannel } from "../api/ws";
import { Button, Card, EmptyState, PageHeader, StateChip } from "../components/ui";

export function InformInspectorPage() {
  const { id } = useParams({ from: "/_app/devices/$id/inform" });
  const navigate = useNavigate();
  const [paused, setPaused] = useState(false);

  const device = useQuery({ queryKey: ["devices", id], queryFn: () => endpoints.devices.get(id) });

  const { state, messages, clear } = useChannel({
    path: paused ? "" : `/ws/devices/${id}/inform/`,
  });

  const force = useMutation({
    mutationFn: () => endpoints.devices.forceInform(id),
  });

  const rows = useMemo(
    () => messages.filter((m) => m.type !== "connection.ready"),
    [messages],
  );

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
            <Link to="/devices/$id" params={{ id }} className="text-sm text-slate-400 hover:text-white">
              ← Device detail
            </Link>
            <Button size="sm" variant="secondary" onClick={() => force.mutate()} disabled={force.isPending}>
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

      <div className="mb-4 flex items-center gap-3 text-sm text-slate-400">
        <span>WebSocket:</span>
        <StateChip state={state} />
        <span className="text-slate-600">·</span>
        <span>
          {rows.length} message{rows.length === 1 ? "" : "s"}
        </span>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No exchanges yet"
          hint="Inform protocol codec is stubbed. Once the engine starts generating real traffic, it will stream here live."
        />
      ) : (
        <Card>
          <ul className="divide-y divide-slate-800">
            {rows.map((m, i) => (
              <li key={`${m.seq ?? i}-${m.ts}`} className="py-3 font-mono text-xs">
                <div className="flex items-center gap-3">
                  <span className="text-slate-500">#{m.seq ?? "?"}</span>
                  <span className="text-slate-400">{m.ts}</span>
                  <span className="rounded bg-indigo-900/40 px-2 py-0.5 text-indigo-300">
                    {m.type}
                  </span>
                </div>
                <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-3 text-[11px] text-slate-300">
                  {JSON.stringify(m.data, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="mt-6 text-xs text-slate-600">
        <Button variant="ghost" size="sm" onClick={() => navigate({ to: "/devices" })}>
          ← All devices
        </Button>
      </div>
    </>
  );
}
