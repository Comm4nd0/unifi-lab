/** Thin fetch wrapper plus the TanStack Query hooks the console runs on. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import type {
  Catalog,
  ClientRow,
  DeviceRow,
  FlowRow,
  LinkRow,
  NetworkRow,
  Simulation,
  Site,
} from "@/types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
  }
}

function describe(body: unknown): string {
  if (typeof body === "string") return body;
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    for (const key of ["detail", "non_field_errors", "a_port", "b_port", "model", "name"]) {
      const value = record[key];
      if (typeof value === "string") return value;
      if (Array.isArray(value) && value.length) return String(value[0]);
      if (value && typeof value === "object") {
        const nested = (value as Record<string, unknown>).detail;
        if (typeof nested === "string") return nested;
      }
    }
    const first = Object.values(record)[0];
    if (Array.isArray(first) && first.length) return String(first[0]);
  }
  return "Something went wrong.";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) throw new ApiError(describe(body), response.status, body);
  return body as T;
}

function send<T>(method: string, path: string, payload?: unknown): Promise<T> {
  return api<T>(path, {
    method,
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
}

export const post = <T,>(path: string, payload?: unknown) => send<T>("POST", path, payload);
export const patch = <T,>(path: string, payload?: unknown) => send<T>("PATCH", path, payload);
export const del = (path: string) => api<null>(path, { method: "DELETE" });

/* ------------------------------------------------------------------ queries */

export const keys = {
  catalog: ["catalog"] as const,
  sites: ["sites"] as const,
  site: (id: number) => ["sites", id] as const,
  simulation: (id: number) => ["simulation", id] as const,
  devices: (id: number) => ["devices", id] as const,
  links: (id: number) => ["links", id] as const,
  clients: (id: number) => ["clients", id] as const,
  flows: (id: number) => ["flows", id] as const,
  networks: (id: number) => ["networks", id] as const,
};

type Options<T> = Omit<UseQueryOptions<T, Error, T, readonly unknown[]>, "queryKey" | "queryFn">;

export function useCatalog() {
  return useQuery({
    queryKey: keys.catalog,
    queryFn: () => api<Catalog>("/catalog/"),
    staleTime: Infinity,
  });
}

export function useSites() {
  return useQuery({ queryKey: keys.sites, queryFn: () => api<Site[]>("/sites/") });
}

export function useSimulation(siteId: number | null, options?: Options<Simulation>) {
  return useQuery({
    queryKey: keys.simulation(siteId ?? 0),
    queryFn: () => api<Simulation>(`/sites/${siteId}/simulation/`),
    enabled: siteId !== null,
    // The simulation is time-varying, so keep it ticking like a live console.
    refetchInterval: 3000,
    ...options,
  });
}

export function useDevices(siteId: number | null) {
  return useQuery({
    queryKey: keys.devices(siteId ?? 0),
    queryFn: () => api<DeviceRow[]>(`/devices/?site=${siteId}`),
    enabled: siteId !== null,
  });
}

export function useLinks(siteId: number | null) {
  return useQuery({
    queryKey: keys.links(siteId ?? 0),
    queryFn: () => api<LinkRow[]>(`/links/?site=${siteId}`),
    enabled: siteId !== null,
  });
}

export function useClients(siteId: number | null) {
  return useQuery({
    queryKey: keys.clients(siteId ?? 0),
    queryFn: () => api<ClientRow[]>(`/clients/?site=${siteId}`),
    enabled: siteId !== null,
  });
}

export function useFlows(siteId: number | null) {
  return useQuery({
    queryKey: keys.flows(siteId ?? 0),
    queryFn: () => api<FlowRow[]>(`/flows/?site=${siteId}`),
    enabled: siteId !== null,
  });
}

export function useNetworks(siteId: number | null) {
  return useQuery({
    queryKey: keys.networks(siteId ?? 0),
    queryFn: () => api<NetworkRow[]>(`/networks/?site=${siteId}`),
    enabled: siteId !== null,
  });
}

/** Invalidate everything that depends on the shape of a site. */
export function useSiteMutation<TArgs = void, TResult = unknown>(
  siteId: number | null,
  fn: (args: TArgs) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation<TResult, Error, TArgs>({
    mutationFn: fn,
    onSuccess: () => {
      // The site list always moves; the per-site queries only when we have one.
      queryClient.invalidateQueries({ queryKey: keys.sites });
      if (siteId === null) return;
      for (const key of [
        keys.simulation(siteId),
        keys.devices(siteId),
        keys.links(siteId),
        keys.clients(siteId),
        keys.flows(siteId),
        keys.networks(siteId),
      ]) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
}
