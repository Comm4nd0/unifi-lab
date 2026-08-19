/** The hardware picker: browse the UniFi catalogue and drop a model into the site. */

import { useMemo, useState } from "react";

import { post, useCatalog, useSiteMutation } from "@/api/client";
import { LINE_ICONS, SearchIcon } from "@/components/icons";
import { Badge, Input, Modal, cx, useToast } from "@/components/ui";
import { speed, watts } from "@/lib/format";
import type { CatalogModel, DeviceLine, DeviceRow } from "@/types";

const LINES: { key: DeviceLine | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "gateway", label: "Gateways" },
  { key: "switch", label: "Switches" },
  { key: "ap", label: "Access points" },
  { key: "protect", label: "Protect" },
  { key: "other", label: "Other" },
];

export function AddDeviceDialog({
  open,
  onClose,
  siteId,
  position,
}: {
  open: boolean;
  onClose: () => void;
  siteId: number | null;
  position?: { x: number; y: number };
}) {
  const toast = useToast();
  const catalog = useCatalog();
  const [line, setLine] = useState<DeviceLine | "all">("all");
  const [query, setQuery] = useState("");

  const add = useSiteMutation(siteId, (model: string) =>
    post<DeviceRow>("/devices/", {
      site: siteId,
      model,
      // With no position the API drops the device into the first free grid slot.
      x: position?.x ?? 0,
      y: position?.y ?? 0,
    }),
  );

  const models = useMemo(() => {
    const all = catalog.data?.models ?? [];
    const needle = query.trim().toLowerCase();
    return all.filter((model) => {
      if (line !== "all" && model.line !== line) return false;
      if (!needle) return true;
      return `${model.name} ${model.short} ${model.family} ${model.description}`
        .toLowerCase()
        .includes(needle);
    });
  }, [catalog.data, line, query]);

  return (
    <Modal open={open} onClose={onClose} title="Add a device" width="max-w-3xl">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <SearchIcon
              size={15}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-500"
            />
            <Input
              autoFocus
              placeholder="Search the catalogue…"
              className="pl-8"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="flex gap-1">
            {LINES.map((item) => (
              <button
                key={item.key}
                onClick={() => setLine(item.key)}
                className={cx(
                  "rounded-md border px-2 py-1 text-xs transition",
                  line === item.key
                    ? "border-unifi bg-unifi/15 text-unifi-bright"
                    : "border-ink-700 text-ink-400 hover:text-ink-200",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid max-h-[52vh] grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
          {models.map((model) => (
            <ModelCard
              key={model.key}
              model={model}
              busy={add.isPending}
              onPick={() =>
                add
                  .mutateAsync(model.key)
                  .then((device) => {
                    toast(`${device.name} added.`);
                    onClose();
                  })
                  .catch((error: Error) => toast(error.message, "bad"))
              }
            />
          ))}
          {!models.length && (
            <p className="col-span-full py-8 text-center text-sm text-ink-500">
              Nothing in the catalogue matches “{query}”.
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}

function ModelCard({
  model,
  onPick,
  busy,
}: {
  model: CatalogModel;
  onPick: () => void;
  busy: boolean;
}) {
  const Icon = LINE_ICONS[model.line] ?? LINE_ICONS.other;
  const fastest = Math.max(...model.ports.map((port) => port.speed_mbps));
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onPick}
      className="flex gap-3 rounded-md border border-ink-800 bg-ink-850/50 p-3 text-left transition hover:border-unifi hover:bg-ink-800 disabled:opacity-50"
    >
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded bg-ink-800 text-unifi-bright">
        <Icon size={17} />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink-100">{model.name}</span>
          <Badge>{model.short}</Badge>
        </div>
        <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-ink-400">
          {model.description}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] text-ink-500">
          <span>
            {model.port_count} port{model.port_count === 1 ? "" : "s"}
          </span>
          <span>· up to {speed(fastest)}</span>
          {model.poe_budget_w > 0 && <span>· {watts(model.poe_budget_w)} PoE</span>}
          {model.poe_in && <span>· needs {model.poe_in}</span>}
          {!model.stp_capable && <span className="text-warn">· no STP</span>}
        </div>
      </div>
    </button>
  );
}
