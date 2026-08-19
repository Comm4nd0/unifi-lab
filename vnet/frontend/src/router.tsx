import type React from "react";
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";

import { AppShell } from "@/components/AppShell";
import { ClientsPage } from "@/routes/Clients";
import { DashboardPage } from "@/routes/Dashboard";
import { DevicesPage } from "@/routes/Devices";
import { InsightsPage } from "@/routes/Insights";
import { SettingsPage } from "@/routes/Settings";
import { TopologyPage } from "@/routes/Topology";
import { TrafficPage } from "@/routes/Traffic";

const rootRoute = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});

/** Generic so each route keeps its literal path in the router's type map. */
const page = <T extends string>(path: T, component: () => React.ReactNode) =>
  createRoute({ getParentRoute: () => rootRoute, path, component });

export const NAV = [
  { path: "/", label: "Dashboard" },
  { path: "/topology", label: "Topology" },
  { path: "/devices", label: "Devices" },
  { path: "/clients", label: "Clients" },
  { path: "/traffic", label: "Traffic" },
  { path: "/insights", label: "Insights" },
  { path: "/settings", label: "Settings" },
] as const;

const routeTree = rootRoute.addChildren([
  page("/", DashboardPage),
  page("/topology", TopologyPage),
  page("/devices", DevicesPage),
  page("/clients", ClientsPage),
  page("/traffic", TrafficPage),
  page("/insights", InsightsPage),
  page("/settings", SettingsPage),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
