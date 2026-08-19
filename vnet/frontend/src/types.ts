/** Types mirroring the payloads served by the Django API. */

export type Severity = "critical" | "warning" | "info";
export type StpMode = "rstp" | "stp" | "disabled";
export type PortState = "forwarding" | "discarding" | "disabled" | "err-disabled";
export type LinkState = "forwarding" | "blocked" | "down";
export type DeviceLine = "gateway" | "switch" | "ap" | "protect" | "other";

export interface IssueSubject {
  kind: "device" | "port" | "link" | "client" | "flow" | "site";
  id: string;
  label: string;
}

export interface Issue {
  code: string;
  severity: Severity;
  category: "stp" | "power" | "capacity" | "topology" | "config" | "general";
  title: string;
  detail: string;
  recommendation: string;
  subjects: IssueSubject[];
  meta: Record<string, unknown>;
}

export interface CatalogPort {
  index: number;
  label: string;
  media: string;
  media_family: string;
  speed_mbps: number;
  role: "lan" | "wan" | "uplink";
  poe_out: string | null;
  poe_max_w: number;
  poe_in: string | null;
}

export interface CatalogModel {
  key: string;
  name: string;
  short: string;
  line: DeviceLine;
  family: string;
  description: string;
  routing: boolean;
  switching: boolean;
  wireless: boolean;
  stp_capable: boolean;
  powered_by: string;
  poe_in: string | null;
  power_draw_w: number;
  poe_budget_w: number;
  switching_capacity_mbps: number;
  wan_capacity_mbps: number;
  wireless_capacity_mbps: number;
  max_wireless_clients: number;
  port_count: number;
  ports: CatalogPort[];
}

export interface Catalog {
  version: string;
  cables: Record<string, number>;
  models: CatalogModel[];
}

export interface Site {
  id: number;
  name: string;
  description: string;
  stp_mode: StpMode;
  wan_download_mbps: number;
  wan_upload_mbps: number;
  device_count: number;
  client_count: number;
}

export interface PortRow {
  id: number;
  device: number;
  device_name: string;
  index: number;
  name: string;
  label: string;
  enabled: boolean;
  poe_enabled: boolean;
  bpdu_guard: boolean;
  speed_override: number | null;
  native_network: number | null;
  media: string;
  role: "lan" | "wan" | "uplink";
  max_speed_mbps: number;
  poe_out: string | null;
  poe_max_w: number;
  poe_in: string | null;
  link_id: number | null;
}

export interface DeviceRow {
  id: number;
  site: number;
  name: string;
  model: string;
  model_name: string;
  short: string;
  line: DeviceLine;
  mac: string;
  ip: string | null;
  x: number;
  y: number;
  enabled: boolean;
  stp_enabled: boolean;
  stp_priority: number;
  note: string;
  ports: PortRow[];
}

export interface LinkRow {
  id: number;
  site: number;
  a_port: number;
  b_port: number;
  a_device: number;
  b_device: number;
  a_label: string;
  b_label: string;
  cable: string;
  enabled: boolean;
}

export interface ClientRow {
  id: number;
  site: number;
  name: string;
  kind: "wired" | "wireless";
  category: string;
  mac: string;
  ip: string | null;
  port: number | null;
  access_point: number | null;
  network: number | null;
  down_mbps: number;
  up_mbps: number;
  rssi_dbm: number;
  device_name: string | null;
}

export interface FlowRow {
  id: number;
  site: number;
  name: string;
  enabled: boolean;
  protocol: string;
  mbps: number;
  burstiness: number;
  src_kind: "client" | "device" | "internet";
  src_client: number | null;
  src_device: number | null;
  dst_kind: "client" | "device" | "internet";
  dst_client: number | null;
  dst_device: number | null;
}

export interface NetworkRow {
  id: number;
  site: number;
  name: string;
  vlan_id: number;
  subnet: string;
  purpose: string;
  isolated: boolean;
}

/* ------------------------------------------------------------ simulation */

export interface SimPort {
  id: string;
  device_id: string;
  index: number;
  label: string;
  media: string;
  role: "lan" | "wan" | "uplink";
  max_speed_mbps: number;
  speed_mbps: number;
  enabled: boolean;
  poe_out: string | null;
  poe_max_w: number;
  poe_enabled: boolean;
  poe_delivered_w: number;
  bpdu_guard: boolean;
  link_id: string | null;
  peer_port_id: string | null;
  peer_device_id: string | null;
  stp_role: string | null;
  stp_state: PortState;
  stp_cost: number;
  stp_reason: string;
  edge: boolean;
  load_mbps: number;
  utilisation: number;
  client_ids: string[];
}

export interface SimDevice {
  id: string;
  name: string;
  model: string;
  model_name: string;
  short: string;
  line: DeviceLine;
  mac: string;
  ip: string;
  x: number;
  y: number;
  status: "online" | "offline" | "error";
  enabled: boolean;
  throughput_mbps: number;
  client_count: number;
  power_draw_w: number;
  poe_used_w: number;
  poe_budget_w: number;
  uplink_device_id: string | null;
  uplink_port_id: string | null;
  uplink_kind: "internet" | "device" | "none";
  stp: {
    device_id: string;
    priority: number;
    bridge_id: string;
    is_root: boolean;
    root_device_id: string;
    root_path_cost: number;
    root_port_id: string | null;
    component: number;
  } | null;
  stp_enabled: boolean;
  stp_priority: number;
  wireless: {
    client_count: number;
    demand_mbps: number;
    capacity_mbps: number;
    utilisation: number;
  } | null;
  ports: SimPort[];
}

export interface SimLink {
  id: string;
  cable: string;
  enabled: boolean;
  state: LinkState;
  speed_mbps: number;
  a_port_id: string;
  b_port_id: string;
  a_device_id: string;
  b_device_id: string;
  a_label: string;
  b_label: string;
  a_stp_role: string | null;
  b_stp_role: string | null;
  load_mbps: number;
  utilisation: number;
  storm: boolean;
}

export interface SimClient {
  id: string;
  name: string;
  kind: "wired" | "wireless";
  mac: string;
  ip: string;
  category: string;
  device_id: string | null;
  device_name: string | null;
  port_id: string | null;
  port_label: string | null;
  rssi_dbm: number | null;
  down_mbps: number;
  up_mbps: number;
  status: "online" | "offline";
}

export interface SimFlowResult {
  id: string;
  label: string;
  kind: string;
  offered_mbps: number;
  delivered_mbps: number;
  loss_pct: number;
  path_device_ids: string[];
  latency_ms: number;
  bottleneck: string | null;
  status: "ok" | "congested" | "dropped";
}

export interface Simulation {
  t: number;
  site: {
    id: string;
    name: string;
    stp_mode: StpMode;
    wan_download_mbps: number;
    wan_upload_mbps: number;
  };
  health: {
    score: number;
    status: "ok" | "warning" | "critical";
    counts: Record<Severity, number>;
    device_count: number;
    client_count: number;
    link_count: number;
    convergence_estimate_s: number;
  };
  devices: SimDevice[];
  links: SimLink[];
  clients: SimClient[];
  stp: {
    mode: StpMode;
    root_device_ids: string[];
    convergence_estimate_s: number;
    bridges: Record<string, SimDevice["stp"]>;
    ports: Record<string, { role: string; state: PortState; reason: string }>;
    loops: string[][];
    active_link_ids: string[];
    blocked_link_ids: string[];
    down_link_ids: string[];
  };
  power: {
    offline_device_ids: string[];
    delivered_w: Record<string, number>;
    pse: Record<
      string,
      { device_id: string; budget_w: number; used_w: number; utilisation: number }
    >;
  };
  traffic: {
    links: Record<
      string,
      {
        link_id: string;
        capacity_mbps: number;
        load_mbps: number;
        utilisation: number;
        offered_utilisation: number;
        storm: boolean;
      }
    >;
    flows: SimFlowResult[];
    device_throughput: Record<string, number>;
    wireless: Record<string, { client_count: number; demand_mbps: number; capacity_mbps: number; utilisation: number }>;
    wan: {
      download_mbps: number;
      upload_mbps: number;
      download_capacity_mbps: number;
      upload_capacity_mbps: number;
      download_utilisation: number;
      upload_utilisation: number;
      gateway_id: string | null;
    };
    history: { t: number; download_mbps: number; upload_mbps: number }[];
  };
  issues: Issue[];
}
