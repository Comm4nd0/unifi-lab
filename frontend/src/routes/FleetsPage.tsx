import { FormEvent, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints } from "../api/client";
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

export function FleetsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["fleets"], queryFn: endpoints.fleets.list });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });
  const blueprints = useQuery({ queryKey: ["blueprints"], queryFn: endpoints.blueprints.list });
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Fleets"
        subtitle="Named collections of virtual devices provisioned together."
        actions={<Button onClick={() => setCreating(true)}>New fleet</Button>}
      />

      {creating && (
        <div className="mb-6">
          <CreateFleetForm
            controllers={controllers.data?.results ?? []}
            blueprints={blueprints.data?.results ?? []}
            onCancel={() => setCreating(false)}
            onCreated={() => {
              setCreating(false);
              qc.invalidateQueries({ queryKey: ["fleets"] });
              qc.invalidateQueries({ queryKey: ["devices"] });
            }}
          />
        </div>
      )}

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.error && (
        <p className="text-sm text-red-400">Failed to load fleets: {(list.error as Error).message}</p>
      )}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No fleets yet"
          hint="Create one to spin up a batch of virtual devices against a controller."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">State</th>
                <th className="px-4 py-2 text-left font-medium">Devices</th>
                <th className="px-4 py-2 text-left font-medium">Source</th>
                <th className="px-4 py-2 text-left font-medium">Controller</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((f) => {
                const ctrl = controllers.data?.results.find((c) => c.id === f.controller_target);
                const bp = f.blueprint
                  ? blueprints.data?.results.find((b) => b.id === f.blueprint)
                  : null;
                return (
                  <tr key={f.id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-medium">
                      <Link to="/fleets/$id" params={{ id: f.id }} className="hover:text-white">
                        {f.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <StateChip state={f.state} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{f.device_count}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {bp ? (
                        <Link
                          to="/blueprints/$id"
                          params={{ id: bp.id }}
                          className="text-indigo-400 hover:text-indigo-300"
                        >
                          {bp.name} (v{bp.version})
                        </Link>
                      ) : (
                        <span className="font-mono">{f.model_code}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {ctrl ? ctrl.name : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to="/fleets/$id"
                        params={{ id: f.id }}
                        className="text-sm text-indigo-400 hover:text-indigo-300"
                      >
                        Detail →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function CreateFleetForm({
  controllers,
  blueprints,
  onCancel,
  onCreated,
}: {
  controllers: { id: string; name: string }[];
  blueprints: { id: string; name: string; version: number }[];
  onCancel: () => void;
  onCreated: () => void;
}) {
  const templates = useQuery({ queryKey: ["templates"], queryFn: endpoints.templates.list });
  const [name, setName] = useState("");
  const [controller, setController] = useState<string>(controllers[0]?.id ?? "");
  const [source, setSource] = useState<"simple" | "blueprint">(
    blueprints.length > 0 ? "blueprint" : "simple",
  );
  const [blueprintId, setBlueprintId] = useState<string>(blueprints[0]?.id ?? "");
  const [modelCode, setModelCode] = useState("USW24P250");
  const [deviceCount, setDeviceCount] = useState(5);
  const [autoAdopt, setAutoAdopt] = useState(false);
  const [rampMode, setRampMode] = useState<"all-at-once" | "linear-1" | "linear-5" | "linear-10">(
    "all-at-once",
  );

  const rampSpec = (() => {
    switch (rampMode) {
      case "linear-1":
        return { mode: "linear", devices_per_sec: 1 };
      case "linear-5":
        return { mode: "linear", devices_per_sec: 5 };
      case "linear-10":
        return { mode: "linear", devices_per_sec: 10 };
      default:
        return { mode: "all-at-once" };
    }
  })();

  const create = useMutation({
    mutationFn: () =>
      endpoints.fleets.create(
        source === "blueprint"
          ? {
              name,
              controller_target: controller,
              blueprint: blueprintId,
              auto_adopt: autoAdopt,
              ramp_spec: rampSpec,
            }
          : {
              name,
              controller_target: controller,
              model_code: modelCode,
              device_count: deviceCount,
              auto_adopt: autoAdopt,
              ramp_spec: rampSpec,
            },
      ),
    onSuccess: onCreated,
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  const canSubmit =
    !!controller && !!name && (source === "simple" || !!blueprintId);

  return (
    <Card>
      <h2 className="text-lg font-semibold">New fleet</h2>
      <p className="mt-1 text-sm text-slate-400">
        Blueprint source materialises one device per entry in{" "}
        <span className="font-mono">site.devices</span>. Simple mode spins up N copies of one model.
      </p>
      <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
        <div className="flex flex-col gap-1.5">
          <Label>Name</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Controller</Label>
          <Select required value={controller} onChange={(e) => setController(e.target.value)}>
            <option value="">— pick a controller —</option>
            {controllers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Source</Label>
          <div className="flex gap-4 text-sm text-slate-200">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                value="blueprint"
                checked={source === "blueprint"}
                onChange={() => setSource("blueprint")}
                disabled={blueprints.length === 0}
              />
              Blueprint {blueprints.length === 0 && <span className="text-slate-500">(none yet)</span>}
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                value="simple"
                checked={source === "simple"}
                onChange={() => setSource("simple")}
              />
              Simple (N × one model)
            </label>
          </div>
        </div>

        {source === "blueprint" ? (
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>Blueprint</Label>
            <Select
              required
              value={blueprintId}
              onChange={(e) => setBlueprintId(e.target.value)}
            >
              <option value="">— pick a blueprint —</option>
              {blueprints.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} (v{b.version})
                </option>
              ))}
            </Select>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Label>Model</Label>
              <Select value={modelCode} onChange={(e) => setModelCode(e.target.value)}>
                {(templates.data?.results ?? []).map((t) => (
                  <option key={t.model_code} value={t.model_code}>
                    {t.model_code} — {t.model_display}
                  </option>
                ))}
                {!templates.data && <option value="USW24P250">USW24P250</option>}
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Device count</Label>
              <Input
                type="number"
                min={1}
                max={500}
                value={deviceCount}
                onChange={(e) => setDeviceCount(Number(e.target.value))}
              />
            </div>
          </>
        )}

        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Ramp</Label>
          <Select value={rampMode} onChange={(e) => setRampMode(e.target.value as typeof rampMode)}>
            <option value="all-at-once">All at once</option>
            <option value="linear-1">Linear — 1 device / sec</option>
            <option value="linear-5">Linear — 5 devices / sec</option>
            <option value="linear-10">Linear — 10 devices / sec</option>
          </Select>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-300 md:col-span-2">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-700 bg-slate-900"
            checked={autoAdopt}
            onChange={(e) => setAutoAdopt(e.target.checked)}
          />
          Auto-adopt (requires controller credentials)
        </label>
        {create.error && (
          <p className="text-sm text-red-400 md:col-span-2">
            {create.error instanceof ApiError ? create.error.message : String(create.error)}
          </p>
        )}
        <div className="flex gap-2 md:col-span-2">
          <Button type="submit" disabled={create.isPending || !canSubmit}>
            {create.isPending ? "Spawning…" : "Spawn fleet"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
