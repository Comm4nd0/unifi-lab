import { FormEvent, useMemo, useState } from "react";
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

export function DevicesPage() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["devices"],
    queryFn: endpoints.devices.list,
    refetchInterval: 10_000,
  });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [controllerFilter, setControllerFilter] = useState("");

  const allDevices = list.data?.results ?? [];

  // Build filter option sets from what's actually present — cheap for
  // the current cluster sizes; upgrade to server-side faceting once we
  // regularly have thousands of devices.
  const availableStates = useMemo(() => {
    const set = new Set<string>();
    for (const d of allDevices) if (d.state) set.add(d.state);
    return Array.from(set).sort();
  }, [allDevices]);

  const filteredDevices = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allDevices.filter((d) => {
      if (stateFilter && d.state !== stateFilter) return false;
      if (controllerFilter && d.controller_target !== controllerFilter) return false;
      if (q) {
        const hay = `${d.mac_address} ${d.hostname ?? ""} ${d.model_code} ${d.serial_number}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [allDevices, search, stateFilter, controllerFilter]);

  const hasFilters = !!(search || stateFilter || controllerFilter);
  const clearFilters = () => {
    setSearch("");
    setStateFilter("");
    setControllerFilter("");
  };

  return (
    <>
      <PageHeader
        title="Devices"
        subtitle="Virtual UniFi devices. Phase 0: they don't transmit until pcaps unlock the codec."
        actions={<Button onClick={() => setCreating(true)}>Add device</Button>}
      />

      {creating && (
        <div className="mb-6">
          <CreateDeviceForm
            controllers={controllers.data?.results ?? []}
            onCancel={() => setCreating(false)}
            onCreated={() => {
              setCreating(false);
              qc.invalidateQueries({ queryKey: ["devices"] });
            }}
          />
        </div>
      )}

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.error && (
        <p className="text-sm text-red-400">Failed to load devices: {(list.error as Error).message}</p>
      )}
      {list.data && allDevices.length === 0 && (
        <EmptyState
          title="No virtual devices yet"
          hint="Add one to reserve a MAC + serial and route it at a controller."
        />
      )}
      {list.data && allDevices.length > 0 && (
        <>
          <Card className="mb-4">
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
              <div>
                <Label>Search</Label>
                <Input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="MAC, hostname, serial, model…"
                />
              </div>
              <div>
                <Label>State</Label>
                <Select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
                  <option value="">All states</option>
                  {availableStates.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Controller</Label>
                <Select
                  value={controllerFilter}
                  onChange={(e) => setControllerFilter(e.target.value)}
                >
                  <option value="">All controllers</option>
                  <option value="__none__" disabled>
                    ──────────
                  </option>
                  {(controllers.data?.results ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>&nbsp;</Label>
                <Button variant="ghost" onClick={clearFilters} disabled={!hasFilters}>
                  Clear filters
                </Button>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Showing {filteredDevices.length.toLocaleString()} of{" "}
              {allDevices.length.toLocaleString()} devices.
            </p>
          </Card>

          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">MAC</th>
                  <th className="px-4 py-2 text-left font-medium">Hostname</th>
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                  <th className="px-4 py-2 text-left font-medium">State</th>
                  <th className="px-4 py-2 text-left font-medium">Controller</th>
                  <th className="px-4 py-2 text-left font-medium">Last heartbeat</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredDevices.map((d) => {
                  const ctrl = controllers.data?.results.find((c) => c.id === d.controller_target);
                  return (
                    <tr key={d.id} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-mono text-xs">
                        <Link to="/devices/$id" params={{ id: d.id }} className="hover:text-white">
                          {d.mac_address}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {d.hostname || <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{d.model_code}</td>
                      <td className="px-4 py-3">
                        <StateChip state={d.state} />
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {ctrl ? ctrl.name : <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">
                        {d.last_heartbeat_at
                          ? new Date(d.last_heartbeat_at).toLocaleString()
                          : "never"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          to="/devices/$id"
                          params={{ id: d.id }}
                          className="text-sm text-indigo-400 hover:text-indigo-300"
                        >
                          Detail →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {filteredDevices.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-sm text-slate-500">
                      No devices match these filters.{" "}
                      <button
                        type="button"
                        onClick={clearFilters}
                        className="text-indigo-400 hover:text-indigo-300"
                      >
                        Clear
                      </button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

function CreateDeviceForm({
  controllers,
  onCancel,
  onCreated,
}: {
  controllers: { id: string; name: string }[];
  onCancel: () => void;
  onCreated: () => void;
}) {
  const templates = useQuery({ queryKey: ["templates"], queryFn: endpoints.templates.list });
  const [modelCode, setModelCode] = useState("USW24P250");
  const [firmware, setFirmware] = useState("");
  const [controller, setController] = useState<string>("");

  const create = useMutation({
    mutationFn: () =>
      endpoints.devices.create({
        model_code: modelCode,
        firmware_version: firmware || undefined,
        controller_target: controller || undefined,
      }),
    onSuccess: onCreated,
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold">New virtual device</h2>
      <p className="mt-1 text-sm text-slate-400">
        MAC address and serial number are generated server-side.
      </p>
      <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
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
          <Label>Firmware version</Label>
          <Input
            placeholder="8.3.42"
            value={firmware}
            onChange={(e) => setFirmware(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Controller target</Label>
          <Select value={controller} onChange={(e) => setController(e.target.value)}>
            <option value="">— unassigned —</option>
            {controllers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
        {create.error && (
          <p className="text-sm text-red-400 md:col-span-2">
            {create.error instanceof ApiError ? create.error.message : String(create.error)}
          </p>
        )}
        <div className="flex gap-2 md:col-span-2">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
