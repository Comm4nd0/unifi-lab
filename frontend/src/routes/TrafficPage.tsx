import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints, type TrafficProfile } from "../api/client";
import { FlowRateChart } from "../components/FlowRateChart";
import {
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  PageHeader,
  Select,
  StateChip,
} from "../components/ui";

const EXAMPLE_PROFILE = `name: iot-baseline
description: Low-rate chatter from typical IoT clients
applies_to:
  vlan: 40
flows:
  - direction: client-to-internet
    app: "Cloud Services"
    dpi_cat: 22
    rate: "2/min"
    bytes_per_flow: "20KB-200KB"
  - direction: client-to-lan
    app: "mDNS"
    rate: "10/min"
    bytes_per_flow: "1-4KB"
    blocked_by_rule: "IoT-to-LAN-default-deny"
`;

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

type Tab = "profiles" | "flows";

export function TrafficPage() {
  const [tab, setTab] = useState<Tab>("profiles");

  return (
    <>
      <PageHeader
        title="Traffic"
        subtitle="Traffic profiles and live flow inspection — Phase 2 authoring surface; runtime injection lands in Phase 3."
      />

      <nav className="mb-6 flex gap-1 border-b border-slate-800">
        {(["profiles", "flows"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              "-mb-px border-b-2 px-4 py-2 text-sm capitalize transition " +
              (tab === t
                ? "border-indigo-500 text-white"
                : "border-transparent text-slate-400 hover:text-slate-200")
            }
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "profiles" ? <ProfilesTab /> : <FlowsTab />}
    </>
  );
}

function ProfilesTab() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["traffic", "profiles"],
    queryFn: endpoints.traffic.profiles.list,
  });
  const [editing, setEditing] = useState<TrafficProfile | "new" | null>(null);

  if (editing) {
    return (
      <ProfileEditor
        profile={editing === "new" ? null : editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          qc.invalidateQueries({ queryKey: ["traffic", "profiles"] });
        }}
      />
    );
  }

  return (
    <>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setEditing("new")}>New profile</Button>
      </div>
      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No traffic profiles yet"
          hint="Author a YAML profile; Phase 3 wires it into per-fleet flow generation."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Version</th>
                <th className="px-4 py-2 text-left font-medium">Flows</th>
                <th className="px-4 py-2 text-left font-medium">Active</th>
                <th className="px-4 py-2 text-left font-medium">Updated</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((p) => {
                const flowCount =
                  Array.isArray((p.parsed_json as { flows?: unknown[] }).flows)
                    ? ((p.parsed_json as { flows: unknown[] }).flows.length as number)
                    : 0;
                return (
                  <tr key={p.id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-medium">{p.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">v{p.version}</td>
                    <td className="px-4 py-3 font-mono text-xs">{flowCount}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {p.is_active ? "yes" : "no"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">
                      {new Date(p.updated_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setEditing(p)}
                        className="text-sm text-indigo-400 hover:text-indigo-300"
                      >
                        Edit →
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

function ProfileEditor({
  profile,
  onClose,
  onSaved,
}: {
  profile: TrafficProfile | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = profile === null;
  const [name, setName] = useState(profile?.name ?? "");
  const [source, setSource] = useState(profile?.source_yaml ?? EXAMPLE_PROFILE);
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const body = { name, source_yaml: source };
      return isNew
        ? endpoints.traffic.profiles.create(body)
        : endpoints.traffic.profiles.update(profile!.id, body);
    },
    onSuccess: onSaved,
    onError: (err) =>
      setFormError(err instanceof ApiError ? err.message : (err as Error).message),
  });

  const del = useMutation({
    mutationFn: () => endpoints.traffic.profiles.delete(profile!.id),
    onSuccess: onSaved,
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    save.mutate();
  };

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {isNew ? "New traffic profile" : `Edit ${profile!.name}`}
        </h2>
        <div className="flex gap-2">
          {!isNew && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                if (confirm(`Delete ${profile!.name}?`)) del.mutate();
              }}
            >
              Delete
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onClose}>
            Back
          </Button>
        </div>
      </div>
      <form className="grid gap-4" onSubmit={onSubmit}>
        <div>
          <Label>Name</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Source YAML</Label>
          <textarea
            className="mt-1 min-h-[24rem] w-full rounded-md border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-100 focus-visible:border-indigo-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            spellCheck={false}
          />
        </div>
        {formError && <p className="text-sm text-red-400">{formError}</p>}
        <div className="flex gap-2">
          <Button type="submit" disabled={save.isPending || !name}>
            {save.isPending ? "Saving…" : isNew ? "Create" : "Save new version"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function FlowsTab() {
  const qc = useQueryClient();
  const fleets = useQuery({ queryKey: ["fleets"], queryFn: endpoints.fleets.list });
  const [fleetId, setFleetId] = useState<string>("");
  const [sampleCount, setSampleCount] = useState(20);
  const [windowMinutes, setWindowMinutes] = useState(60);

  const flows = useQuery({
    queryKey: ["traffic", "flows", { fleetId }],
    queryFn: () => endpoints.traffic.flows(fleetId ? { fleet: fleetId } : {}),
    refetchInterval: 5_000,
  });

  const stats = useQuery({
    queryKey: ["traffic", "flows", "stats", { fleetId, windowMinutes }],
    queryFn: () =>
      endpoints.traffic.stats({
        fleet: fleetId || undefined,
        window_minutes: windowMinutes,
        bucket_seconds: windowMinutes <= 15 ? 30 : windowMinutes <= 120 ? 60 : 300,
      }),
    refetchInterval: 5_000,
  });

  const generate = useMutation({
    mutationFn: () =>
      endpoints.traffic.generateSamples({ fleet_id: fleetId, count: sampleCount }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["traffic", "flows"] }),
  });

  return (
    <>
      <Card className="mb-4">
        <div className="grid gap-4 md:grid-cols-[1fr_8rem_auto]">
          <div>
            <Label>Fleet</Label>
            <Select value={fleetId} onChange={(e) => setFleetId(e.target.value)}>
              <option value="">— all fleets —</option>
              {(fleets.data?.results ?? []).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Sample count</Label>
            <Input
              type="number"
              min={1}
              max={500}
              value={sampleCount}
              onChange={(e) => setSampleCount(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="secondary"
              onClick={() => generate.mutate()}
              disabled={!fleetId || generate.isPending}
            >
              {generate.isPending ? "Generating…" : "Generate samples"}
            </Button>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Generate samples is a dev convenience — the worker ticker also writes real flows from
          active traffic profiles every few seconds.
        </p>
      </Card>

      {stats.data && (
        <Card className="mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
                Flow rate
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                {stats.data.totals.allowed.toLocaleString()} allowed ·{" "}
                {stats.data.totals.blocked.toLocaleString()} blocked over the last{" "}
                {stats.data.window_minutes} minutes
              </p>
            </div>
            <Select
              value={String(windowMinutes)}
              onChange={(e) => setWindowMinutes(Number(e.target.value))}
              className="w-auto"
            >
              <option value="15">15 min</option>
              <option value="60">1 hour</option>
              <option value="240">4 hours</option>
              <option value="1440">24 hours</option>
            </Select>
          </div>
          <div className="mt-3">
            <FlowRateChart stats={stats.data} />
          </div>
        </Card>
      )}

      {flows.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {flows.data && flows.data.results.length === 0 && (
        <EmptyState
          title="No flows yet"
          hint={
            fleetId
              ? "Click Generate samples to seed some, or wait for the Traffic Simulator."
              : "Pick a fleet and generate samples, or select one above."
          }
        />
      )}
      {flows.data && flows.data.results.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-3 py-2 text-left font-medium">App</th>
                <th className="px-3 py-2 text-left font-medium">Proto</th>
                <th className="px-3 py-2 text-left font-medium">Source</th>
                <th className="px-3 py-2 text-left font-medium">Dest</th>
                <th className="px-3 py-2 text-right font-medium">Tx</th>
                <th className="px-3 py-2 text-right font-medium">Rx</th>
                <th className="px-3 py-2 text-left font-medium">State</th>
                <th className="px-3 py-2 text-left font-medium">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {flows.data.results.map((f) => (
                <tr key={f.id} className={f.blocked ? "bg-red-950/30" : "hover:bg-slate-900/40"}>
                  <td className="px-3 py-2">{f.application || <span className="text-slate-600">—</span>}</td>
                  <td className="px-3 py-2 font-mono text-xs uppercase">{f.protocol}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {f.src_ip}
                    {f.src_port ? `:${f.src_port}` : ""}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {f.dst_ip}
                    {f.dst_port ? `:${f.dst_port}` : ""}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-400">
                    {humanBytes(f.bytes_tx)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-400">
                    {humanBytes(f.bytes_rx)}
                  </td>
                  <td className="px-3 py-2">
                    <StateChip state={f.blocked ? "error" : "ok"} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {new Date(f.reported_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
