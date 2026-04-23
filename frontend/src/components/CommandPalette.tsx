import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";

type CommandItem = {
  key: string;
  label: string;
  group: string;
  hint?: string;
  /** Invoked on Enter / click. */
  run: () => void;
};

/**
 * Global Cmd/Ctrl-K palette. Opens a centred modal with fuzzy-ish text
 * filtering across fleets, blueprints, devices, controllers, plus a
 * few static "Go to" actions. Arrow keys move the cursor, Enter runs,
 * Esc closes.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  // Open / close key handler.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toLowerCase().includes("mac");
      const comboPressed = (isMac ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === "k";
      if (comboPressed) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      // focus on the next tick so the input exists in the DOM.
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Data — only fetched while the palette is open, so the page isn't
  // hammering the API for a feature no one's using.
  const fleets = useQuery({
    queryKey: ["fleets"],
    queryFn: endpoints.fleets.list,
    enabled: open,
  });
  const blueprints = useQuery({
    queryKey: ["blueprints"],
    queryFn: endpoints.blueprints.list,
    enabled: open,
  });
  const devices = useQuery({
    queryKey: ["devices"],
    queryFn: endpoints.devices.list,
    enabled: open,
  });
  const controllers = useQuery({
    queryKey: ["controllers"],
    queryFn: endpoints.controllers.list,
    enabled: open,
  });

  const close = () => setOpen(false);

  const commands = useMemo<CommandItem[]>(() => {
    const go = (to: string, search?: Record<string, unknown>): (() => void) => () => {
      navigate({ to, search } as never);
      close();
    };
    const items: CommandItem[] = [
      { key: "nav:/", label: "Dashboard", group: "Go to", run: go("/") },
      {
        key: "nav:/controllers",
        label: "Controllers",
        group: "Go to",
        run: go("/controllers"),
      },
      {
        key: "nav:/blueprints",
        label: "Blueprints",
        group: "Go to",
        run: go("/blueprints"),
      },
      {
        key: "nav:/fleets",
        label: "Fleets",
        group: "Go to",
        run: go("/fleets", { blueprint: undefined }),
      },
      { key: "nav:/devices", label: "Devices", group: "Go to", run: go("/devices") },
      { key: "nav:/topology", label: "Topology", group: "Go to", run: go("/topology") },
      { key: "nav:/traffic", label: "Traffic", group: "Go to", run: go("/traffic") },
      { key: "nav:/firmware", label: "Firmware", group: "Go to", run: go("/firmware") },
      { key: "nav:/audit", label: "Audit log", group: "Go to", run: go("/audit") },
      { key: "nav:/tokens", label: "API tokens", group: "Go to", run: go("/tokens") },
      {
        key: "action:new-blueprint",
        label: "New blueprint",
        group: "Actions",
        hint: "Create a blueprint",
        run: go("/blueprints/new"),
      },
    ];
    for (const f of fleets.data?.results ?? []) {
      items.push({
        key: `fleet:${f.id}`,
        label: f.name,
        group: "Fleets",
        hint: `${f.device_count} × ${f.model_code} · ${f.state}`,
        run: () => {
          navigate({ to: "/fleets/$id", params: { id: f.id } });
          close();
        },
      });
    }
    for (const b of blueprints.data?.results ?? []) {
      items.push({
        key: `bp:${b.id}`,
        label: b.name,
        group: "Blueprints",
        hint: `v${b.version}`,
        run: () => {
          navigate({ to: "/blueprints/$id", params: { id: b.id } });
          close();
        },
      });
    }
    for (const d of devices.data?.results ?? []) {
      items.push({
        key: `device:${d.id}`,
        label: d.hostname || d.mac_address,
        group: "Devices",
        hint: `${d.model_code} · ${d.state}${d.hostname ? ` · ${d.mac_address}` : ""}`,
        run: () => {
          navigate({ to: "/devices/$id", params: { id: d.id } });
          close();
        },
      });
    }
    for (const c of controllers.data?.results ?? []) {
      items.push({
        key: `ctrl:${c.id}`,
        label: c.name,
        group: "Controllers",
        hint: `${c.kind} · ${c.health}`,
        run: () => {
          navigate({ to: "/controllers/$id", params: { id: c.id } });
          close();
        },
      });
    }
    return items;
  }, [fleets.data, blueprints.data, devices.data, controllers.data, navigate]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => {
      const hay = `${c.label} ${c.group} ${c.hint ?? ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [commands, query]);

  // Reset cursor when the filter shrinks below the current index.
  useEffect(() => {
    if (cursor >= filtered.length) setCursor(0);
  }, [filtered.length, cursor]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, Math.max(0, filtered.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const picked = filtered[cursor];
      if (picked) picked.run();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  // Group consecutive items of the same group for readable section headers.
  const grouped: { group: string; items: CommandItem[] }[] = [];
  let currentGroup: string | null = null;
  for (const item of filtered) {
    if (item.group !== currentGroup) {
      grouped.push({ group: item.group, items: [] });
      currentGroup = item.group;
    }
    grouped[grouped.length - 1].items.push(item);
  }

  // Absolute index within ``filtered`` so we can mark the cursor correctly
  // while we walk grouped sections.
  let idx = 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-[12vh]"
      onClick={close}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-slate-800 px-3 py-2">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search fleets, blueprints, devices, or type a nav target…"
            className="w-full bg-transparent px-1 py-1 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
            spellCheck={false}
          />
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-1">
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-center text-xs text-slate-500">
              No matches for "{query}".
            </p>
          )}
          {grouped.map((section) => (
            <div key={section.group}>
              <p className="px-4 pt-3 pb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                {section.group}
              </p>
              <ul>
                {section.items.map((item) => {
                  const thisIndex = idx;
                  idx += 1;
                  const isActive = thisIndex === cursor;
                  return (
                    <li
                      key={item.key}
                      onMouseEnter={() => setCursor(thisIndex)}
                      onClick={item.run}
                      className={
                        "flex cursor-pointer items-center justify-between px-4 py-1.5 text-sm " +
                        (isActive
                          ? "bg-indigo-600/30 text-white"
                          : "text-slate-300 hover:bg-slate-900")
                      }
                    >
                      <span className="truncate">{item.label}</span>
                      {item.hint && (
                        <span className="ml-3 truncate font-mono text-[10px] text-slate-500">
                          {item.hint}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-slate-800 px-4 py-2 text-[10px] text-slate-500">
          <kbd className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 font-mono">
            ↑↓
          </kbd>{" "}
          move ·{" "}
          <kbd className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 font-mono">
            Enter
          </kbd>{" "}
          run ·{" "}
          <kbd className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 font-mono">
            Esc
          </kbd>{" "}
          close
        </div>
      </div>
    </div>
  );
}
