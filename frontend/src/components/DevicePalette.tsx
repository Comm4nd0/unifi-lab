import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { endpoints, type DeviceTemplate } from "../api/client";
import { Input } from "./ui";

const FAMILY_GLYPH: Record<string, string> = {
  gateway: "⬒",
  switch: "▣",
  ap: "✦",
  other: "○",
};

const FAMILY_COLOR: Record<string, string> = {
  gateway: "#4f46e5",
  switch: "#0891b2",
  ap: "#059669",
  other: "#64748b",
};

const FAMILY_LABEL: Record<string, string> = {
  gateway: "Gateways",
  switch: "Switches",
  ap: "Access points",
  other: "Other",
};

// Render order — broadly top-of-stack down: gateway, switch, AP, other.
const FAMILY_ORDER = ["gateway", "switch", "ap", "other"];

/**
 * Sidebar list of draggable device templates. Cards are grouped by family
 * with a search box at the top for fast filtering. Each card is an HTML5
 * drag source; the canvas picks up ``model_code`` + ``device_family``
 * from ``dataTransfer`` on drop and builds a new blueprint device.
 */
export function DevicePalette() {
  const templates = useQuery({
    queryKey: ["templates"],
    queryFn: endpoints.templates.list,
  });
  const [query, setQuery] = useState("");

  const onDragStart = (e: React.DragEvent<HTMLDivElement>, t: DeviceTemplate) => {
    e.dataTransfer.setData("application/x-uvl-template", t.model_code);
    e.dataTransfer.setData("application/x-uvl-family", t.device_family);
    e.dataTransfer.effectAllowed = "copy";
  };

  const grouped = useMemo(() => {
    const all = templates.data?.results ?? [];
    const q = query.trim().toLowerCase();
    const matches = q
      ? all.filter((t) => {
          const hay = `${t.model_code} ${t.model_display} ${t.device_family}`.toLowerCase();
          return hay.includes(q);
        })
      : all;
    const buckets: Record<string, DeviceTemplate[]> = {};
    for (const t of matches) {
      const key = FAMILY_LABEL[t.device_family] ? t.device_family : "other";
      (buckets[key] = buckets[key] ?? []).push(t);
    }
    return FAMILY_ORDER.filter((f) => buckets[f]?.length).map((f) => ({
      family: f,
      label: FAMILY_LABEL[f] ?? FAMILY_LABEL.other,
      items: buckets[f],
    }));
  }, [templates.data, query]);

  const totalMatches = grouped.reduce((n, g) => n + g.items.length, 0);

  return (
    <aside className="flex h-full flex-col">
      <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
        Device palette
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        Drag onto the canvas to add. Drop on an existing node for a downstream child.
      </p>
      <div className="mt-3">
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter models…"
          spellCheck={false}
        />
      </div>
      <div className="mt-3 flex flex-col gap-4 overflow-y-auto pr-1">
        {templates.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {templates.error && (
          <p className="text-sm text-red-400">
            {(templates.error as Error).message}
          </p>
        )}
        {templates.data && totalMatches === 0 && (
          <p className="text-sm text-slate-500">
            {query
              ? `No models match "${query}".`
              : "No device templates registered. Add some via the Django admin."}
          </p>
        )}
        {grouped.map((group) => (
          <section key={group.family}>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
              {group.label}
              <span className="ml-2 font-mono text-slate-600">{group.items.length}</span>
            </p>
            <div className="flex flex-col gap-2">
              {group.items.map((t) => {
                const glyph = FAMILY_GLYPH[t.device_family] ?? FAMILY_GLYPH.other;
                const color = FAMILY_COLOR[t.device_family] ?? FAMILY_COLOR.other;
                return (
                  <div
                    key={t.id}
                    draggable
                    onDragStart={(e) => onDragStart(e, t)}
                    className="flex cursor-grab items-center gap-3 rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs shadow hover:border-slate-700 active:cursor-grabbing"
                    title={`${t.model_display} (${t.model_code})`}
                  >
                    <span className="text-lg" style={{ color }}>
                      {glyph}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm text-slate-100">{t.model_display}</p>
                      <p className="truncate font-mono text-[10px] text-slate-500">
                        {t.model_code}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </aside>
  );
}
