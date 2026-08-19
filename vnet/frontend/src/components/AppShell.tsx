import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import { post, useSimulation, useSites, useSiteMutation } from "@/api/client";
import {
  ClientsIcon,
  DashboardIcon,
  DevicesIcon,
  InsightsIcon,
  SettingsIcon,
  TopologyIcon,
  TrafficIcon,
} from "@/components/icons";
import { Badge, Button, Field, Input, Panel, Select, cx, useToast } from "@/components/ui";
import { mbps } from "@/lib/format";
import { useUi } from "@/store";
import type { Site } from "@/types";

const NAV = [
  { to: "/", label: "Dashboard", Icon: DashboardIcon },
  { to: "/topology", label: "Topology", Icon: TopologyIcon },
  { to: "/devices", label: "Devices", Icon: DevicesIcon },
  { to: "/clients", label: "Clients", Icon: ClientsIcon },
  { to: "/traffic", label: "Traffic", Icon: TrafficIcon },
  { to: "/insights", label: "Insights", Icon: InsightsIcon },
  { to: "/settings", label: "Settings", Icon: SettingsIcon },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const sites = useSites();
  const { siteId, setSite } = useUi();

  // Pick a site automatically so the console is never pointing at nothing.
  useEffect(() => {
    if (!sites.data) return;
    const known = sites.data.some((site) => site.id === siteId);
    if (!known) setSite(sites.data[0]?.id ?? null);
  }, [sites.data, siteId, setSite]);

  if (sites.isLoading) {
    return <Splash message="Connecting to the lab…" />;
  }
  if (sites.isError) {
    return (
      <Splash
        message="The API is not answering."
        detail="Start it with `uv run python manage.py runserver 0.0.0.0:8003` in vnet/backend."
      />
    );
  }
  if (!sites.data?.length) {
    return <Onboarding />;
  }

  return (
    <div className="flex h-full">
      <Sidebar sites={sites.data} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

function Splash({ message, detail }: { message: string; detail?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <div className="text-sm text-ink-300">{message}</div>
      {detail && <div className="max-w-md text-xs text-ink-500">{detail}</div>}
    </div>
  );
}

function Sidebar({ sites }: { sites: Site[] }) {
  const { siteId, setSite } = useUi();
  const location = useRouterState({ select: (state) => state.location.pathname });

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-ink-800 bg-ink-900">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="grid h-7 w-7 place-items-center rounded bg-unifi text-xs font-bold text-white">
          U
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-ink-100">Virtual Lab</div>
          <div className="text-[10px] uppercase tracking-wider text-ink-500">Network</div>
        </div>
      </div>

      <div className="px-3 pb-3">
        <Select
          value={siteId ?? ""}
          onChange={(event) => setSite(Number(event.target.value))}
          aria-label="Site"
        >
          {sites.map((site) => (
            <option key={site.id} value={site.id}>
              {site.name}
            </option>
          ))}
        </Select>
      </div>

      <nav className="flex-1 space-y-0.5 px-2">
        {NAV.map(({ to, label, Icon }) => {
          const active = to === "/" ? location === "/" : location.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              className={cx(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition",
                active
                  ? "bg-unifi/15 text-unifi-bright font-medium"
                  : "text-ink-300 hover:bg-ink-850 hover:text-ink-100",
              )}
            >
              <Icon size={17} />
              {label}
            </Link>
          );
        })}
      </nav>

      <SidebarFooter />
    </aside>
  );
}

function SidebarFooter() {
  const { siteId } = useUi();
  const simulation = useSimulation(siteId);
  const health = simulation.data?.health;
  if (!health) return <div className="h-16" />;

  const tone = health.status === "ok" ? "ok" : health.status === "warning" ? "warn" : "bad";
  return (
    <div className="border-t border-ink-800 px-4 py-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-400">Network health</span>
        <Badge tone={tone}>{health.score}/100</Badge>
      </div>
      <div className="mt-2 flex gap-3 text-[11px] text-ink-500">
        <span>{health.device_count} devices</span>
        <span>{health.client_count} clients</span>
      </div>
    </div>
  );
}

function TopBar() {
  const { siteId } = useUi();
  const simulation = useSimulation(siteId);
  const location = useRouterState({ select: (state) => state.location.pathname });
  const current = NAV.find((item) =>
    item.to === "/" ? location === "/" : location.startsWith(item.to),
  );
  const wan = simulation.data?.traffic.wan;
  const counts = simulation.data?.health.counts;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-ink-800 bg-ink-900/60 px-5 backdrop-blur">
      <h1 className="text-base font-semibold text-ink-100">{current?.label ?? "Console"}</h1>
      <div className="flex items-center gap-4">
        {wan && (
          <div className="hidden items-center gap-4 text-xs text-ink-400 sm:flex">
            <span className="tabular-nums">
              <span className="text-ink-500">WAN ↓</span> {mbps(wan.download_mbps)}
            </span>
            <span className="tabular-nums">
              <span className="text-ink-500">↑</span> {mbps(wan.upload_mbps)}
            </span>
          </div>
        )}
        {counts && (counts.critical > 0 || counts.warning > 0) && (
          <Link to="/insights" className="flex items-center gap-1.5">
            {counts.critical > 0 && <Badge tone="critical">{counts.critical} critical</Badge>}
            {counts.warning > 0 && <Badge tone="warning">{counts.warning} warning</Badge>}
          </Link>
        )}
        <span className="flex items-center gap-1.5 text-[11px] text-ink-500">
          <span
            className={cx(
              "h-1.5 w-1.5 rounded-full",
              simulation.isFetching ? "bg-unifi-bright animate-pulse" : "bg-ok",
            )}
          />
          Live
        </span>
      </div>
    </header>
  );
}

function Onboarding() {
  const toast = useToast();
  const { setSite } = useUi();
  const [name, setName] = useState("My Network");

  const seed = useSiteMutation(null, () =>
    post<Site>("/sites/seed-demo/", { name: "Chiltern View" }),
  );
  const create = useSiteMutation(null, (siteName: string) =>
    post<Site>("/sites/", { name: siteName }),
  );

  const adopt = (site: Site) => {
    setSite(site.id);
    toast(`Site "${site.name}" is ready.`);
  };

  return (
    <div className="grid h-full place-items-center p-6">
      <Panel
        title="Welcome to UniFi Virtual Lab"
        subtitle="Build a UniFi network out of real hardware models and see how it behaves."
        className="w-full max-w-xl"
      >
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-medium text-ink-200">Start with an example</h3>
            <p className="mt-1 text-xs text-ink-400">
              A gateway, a core switch, an access switch and two access points — including a
              redundant run so you can watch RSTP block a port.
            </p>
            <Button
              variant="primary"
              className="mt-3"
              disabled={seed.isPending}
              onClick={() => seed.mutateAsync().then(adopt)}
            >
              {seed.isPending ? "Building…" : "Load the example site"}
            </Button>
          </div>

          <div className="border-t border-ink-800 pt-5">
            <h3 className="text-sm font-medium text-ink-200">Or start from nothing</h3>
            <div className="mt-3 flex items-end gap-2">
              <Field label="Site name" className="flex-1">
                <Input value={name} onChange={(event) => setName(event.target.value)} />
              </Field>
              <Button
                disabled={!name.trim() || create.isPending}
                onClick={() => create.mutateAsync(name.trim()).then(adopt)}
              >
                Create
              </Button>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}
