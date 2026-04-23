import {
  createRootRoute,
  createRoute,
  createRouter,
  Navigate,
  Outlet,
  redirect,
} from "@tanstack/react-router";

import { useAuth } from "../store/auth";
import { AppShell } from "./AppShell";
import { LoginPage } from "./LoginPage";
import { DashboardPage } from "./DashboardPage";
import { ControllersPage } from "./ControllersPage";
import { ControllerDetailPage } from "./ControllerDetailPage";
import { DevicesPage } from "./DevicesPage";
import { DeviceDetailPage } from "./DeviceDetailPage";
import { InformInspectorPage } from "./InformInspectorPage";
import { FleetsPage } from "./FleetsPage";
import { FleetDetailPage } from "./FleetDetailPage";
import { FirmwarePage } from "./FirmwarePage";
import { BlueprintsPage } from "./BlueprintsPage";
import { BlueprintEditorPage } from "./BlueprintEditorPage";
import { AuditPage } from "./AuditPage";
import { TopologyPage } from "./TopologyPage";
import { TrafficPage } from "./TrafficPage";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
  validateSearch: (search: Record<string, unknown>) => ({
    redirect: typeof search.redirect === "string" ? search.redirect : undefined,
  }),
});

// Authenticated shell — every route below this checks that we have an access token.
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "_app",
  component: AppShell,
  beforeLoad: ({ location }) => {
    const { access } = useAuth.getState();
    if (!access) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
  },
});

const indexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: DashboardPage,
});

const controllersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/controllers",
  component: ControllersPage,
});

const controllerDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/controllers/$id",
  component: ControllerDetailPage,
});

const devicesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/devices",
  component: DevicesPage,
});

const deviceDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/devices/$id",
  component: DeviceDetailPage,
});

const deviceInformRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/devices/$id/inform",
  component: InformInspectorPage,
});

const fleetsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/fleets",
  component: FleetsPage,
  validateSearch: (search: Record<string, unknown>) => ({
    blueprint: typeof search.blueprint === "string" ? search.blueprint : undefined,
  }),
});

const fleetDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/fleets/$id",
  component: FleetDetailPage,
});

const firmwareRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/firmware",
  component: FirmwarePage,
});

const blueprintsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/blueprints",
  component: BlueprintsPage,
});

const blueprintNewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/blueprints/new",
  component: BlueprintEditorPage,
});

const blueprintEditorRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/blueprints/$id",
  component: BlueprintEditorPage,
});

const trafficRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/traffic",
  component: TrafficPage,
});

const topologyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/topology",
  component: TopologyPage,
});

const auditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audit",
  component: AuditPage,
});

const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "*",
  component: () => <Navigate to="/" />,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    indexRoute,
    controllersRoute,
    controllerDetailRoute,
    devicesRoute,
    deviceDetailRoute,
    deviceInformRoute,
    fleetsRoute,
    fleetDetailRoute,
    firmwareRoute,
    blueprintsRoute,
    blueprintNewRoute,
    blueprintEditorRoute,
    trafficRoute,
    topologyRoute,
    auditRoute,
  ]),
  notFoundRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
