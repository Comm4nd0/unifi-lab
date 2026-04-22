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
  ]),
  notFoundRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
