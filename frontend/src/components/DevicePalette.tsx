import { useQuery } from "@tanstack/react-query";

import { endpoints, type DeviceTemplate } from "../api/client";

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

/**
 * Sidebar list of draggable device templates. Each card is an HTML5
 * drag source; the canvas picks up ``model_code`` + ``device_family``
 * from ``dataTransfer`` on drop and builds a new blueprint device.
 */
export function DevicePalette() {
  const templates = useQuery({
    queryKey: ["templates"],
    queryFn: endpoints.templates.list,
  });

  const onDragStart = (e: React.DragEvent<HTMLDivElement>, t: DeviceTemplate) => {
    e.dataTransfer.setData("application/x-uvl-template", t.model_code);
    e.dataTransfer.setData("application/x-uvl-family", t.device_family);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <aside className="flex h-full flex-col">
      <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
        Device palette
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        Drag onto the canvas to add. Drop on an existing node to create a downstream child.
      </p>
      <div className="mt-3 flex flex-col gap-2">
        {templates.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {templates.error && (
          <p className="text-sm text-red-400">
            {(templates.error as Error).message}
          </p>
        )}
        {templates.data?.results.map((t) => {
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
                  {t.model_code} · {t.device_family}
                </p>
              </div>
            </div>
          );
        })}
        {templates.data && templates.data.results.length === 0 && (
          <p className="text-sm text-slate-500">
            No device templates registered. Add some via the Django admin.
          </p>
        )}
      </div>
    </aside>
  );
}
