import { useAuth } from "../store/auth";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const { refresh, setTokens, clear } = useAuth.getState();
  if (!refresh) return null;
  try {
    const resp = await fetch("/api/v1/auth/jwt/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!resp.ok) {
      clear();
      return null;
    }
    const data = (await resp.json()) as { access: string; refresh?: string };
    setTokens(data.access, data.refresh ?? refresh);
    return data.access;
  } catch {
    clear();
    return null;
  }
}

type RequestOptions = RequestInit & { skipAuth?: boolean };

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const doFetch = async (access: string | null): Promise<Response> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    };
    // Caller can blank Content-Type to let the browser pick the multipart boundary.
    if (headers["Content-Type"] === "") delete headers["Content-Type"];
    if (access && !init?.skipAuth) {
      headers.Authorization = `Bearer ${access}`;
    }
    return fetch(path, { ...init, headers });
  };

  const { access } = useAuth.getState();
  let resp = await doFetch(access);

  if (resp.status === 401 && !init?.skipAuth) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      resp = await doFetch(newAccess);
    }
  }

  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = await resp.text();
    }
    const message =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `${resp.status} ${resp.statusText}`;
    throw new ApiError(resp.status, message, body);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}), ...opts }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  // Multipart form uploads — don't stringify, let fetch set Content-Type
  // with the boundary.
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, {
      method: "POST",
      body: form,
      headers: { "Content-Type": "" }, // Clearing triggers browser-set multipart boundary.
    }),
};

// ── Typed resource shapes (subset matching what the UI needs) ────────
// These intentionally don't import from the generated schema because the
// generated types are unions with many optional fields; these trimmed
// aliases match what the backend actually returns on the hot paths.

export type HealthResponse = {
  status: string;
  db: string;
  redis: string;
  version: string;
};

export type JwtPair = { access: string; refresh: string };

export type User = {
  id: string;
  email: string;
  is_admin: boolean;
  created_at: string;
};

export type ControllerTarget = {
  id: string;
  name: string;
  kind: "uos-server" | "legacy-network";
  inform_url: string;
  api_url: string;
  verify_tls: boolean;
  is_active: boolean;
  health: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
};

export type VirtualDevice = {
  id: string;
  mac_address: string;
  serial_number: string;
  model_code: string;
  firmware_version: string;
  state: string;
  controller_target: string | null;
  fleet: string | null;
  last_heartbeat_at: string | null;
  last_config_applied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DeviceTemplate = {
  id: string;
  model_code: string;
  model_display: string;
  device_family: "ap" | "switch" | "gateway" | "other";
};

export type Blueprint = {
  id: string;
  name: string;
  source_yaml: string;
  parsed_json: Record<string, unknown>;
  version: number;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type BlueprintValidationIssue = {
  severity: "error" | "warning";
  path: string;
  message: string;
};

export type BlueprintValidationResult = {
  valid: boolean;
  parsed: Record<string, unknown> | null;
  issues: BlueprintValidationIssue[];
};

export type FirmwareBlob = {
  id: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  model_codes: string[];
  version: string;
  state: "uploaded" | "ingesting" | "ready" | "failed";
  ingest_error: string;
  created_at: string;
  updated_at: string;
};

export type Fleet = {
  id: string;
  name: string;
  controller_target: string;
  blueprint: string | null;
  model_code: string;
  state: string;
  device_count: number;
  ramp_spec: Record<string, unknown>;
  auto_adopt: boolean;
  retired_at: string | null;
  device_states: Record<string, number>;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const endpoints = {
  jwtCreate: (email: string, password: string) =>
    api.post<JwtPair>("/api/v1/auth/jwt/create/", { email, password }, { skipAuth: true }),
  me: () => api.get<User>("/api/v1/auth/me/"),
  health: () => api.get<HealthResponse>("/api/v1/system/health/"),
  controllers: {
    list: () => api.get<Paginated<ControllerTarget>>("/api/v1/controllers/"),
    get: (id: string) => api.get<ControllerTarget>(`/api/v1/controllers/${id}/`),
    create: (body: Partial<ControllerTarget> & { api_username?: string; api_password?: string }) =>
      api.post<ControllerTarget>("/api/v1/controllers/", body),
    delete: (id: string) => api.delete<void>(`/api/v1/controllers/${id}/`),
  },
  devices: {
    list: () => api.get<Paginated<VirtualDevice>>("/api/v1/devices/"),
    get: (id: string) => api.get<VirtualDevice>(`/api/v1/devices/${id}/`),
    create: (body: { model_code: string; firmware_version?: string; controller_target?: string }) =>
      api.post<VirtualDevice>("/api/v1/devices/", body),
    delete: (id: string) => api.delete<void>(`/api/v1/devices/${id}/`),
    forceInform: (id: string) =>
      api.post<{ accepted: boolean; device_id: string }>(`/api/v1/devices/${id}/force-inform/`),
  },
  templates: {
    list: () => api.get<Paginated<DeviceTemplate>>("/api/v1/templates/"),
  },
  blueprints: {
    list: () => api.get<Paginated<Blueprint>>("/api/v1/blueprints/"),
    get: (id: string) => api.get<Blueprint>(`/api/v1/blueprints/${id}/`),
    create: (body: { name: string; source_yaml: string }) =>
      api.post<Blueprint>("/api/v1/blueprints/", body),
    update: (id: string, body: { name: string; source_yaml: string }) =>
      api.put<Blueprint>(`/api/v1/blueprints/${id}/`, body),
    delete: (id: string) => api.delete<void>(`/api/v1/blueprints/${id}/`),
    validate: (source_yaml: string) =>
      api.post<BlueprintValidationResult>("/api/v1/blueprints/validate/", { source_yaml }),
  },
  firmware: {
    list: () => api.get<Paginated<FirmwareBlob>>("/api/v1/firmware/"),
    get: (id: string) => api.get<FirmwareBlob>(`/api/v1/firmware/${id}/`),
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.postForm<FirmwareBlob>("/api/v1/firmware/", form);
    },
    delete: (id: string) => api.delete<void>(`/api/v1/firmware/${id}/`),
  },
  fleets: {
    list: () => api.get<Paginated<Fleet>>("/api/v1/fleets/"),
    get: (id: string) => api.get<Fleet>(`/api/v1/fleets/${id}/`),
    create: (body: {
      name: string;
      controller_target: string;
      model_code: string;
      device_count: number;
      auto_adopt?: boolean;
    }) => api.post<Fleet>("/api/v1/fleets/", body),
    pause: (id: string) => api.post<Fleet>(`/api/v1/fleets/${id}/pause/`),
    resume: (id: string) => api.post<Fleet>(`/api/v1/fleets/${id}/resume/`),
    teardown: (id: string) => api.post<Fleet>(`/api/v1/fleets/${id}/teardown/`),
    delete: (id: string) => api.delete<void>(`/api/v1/fleets/${id}/`),
  },
};
