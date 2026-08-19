"""Traffic simulation over the converged forwarding topology.

Load is placed on the spanning tree that STP actually left forwarding, so a
blocked port carries nothing — exactly as it would on the real network. When
the offered load exceeds a link's capacity, every flow crossing that link is
scaled back by the same factor, which is a reasonable stand-in for what TCP
does to a saturated uplink.
"""

from __future__ import annotations

import math
import zlib
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from simcore.issues import Issue, Severity, Subject
from simcore.stp import StpResult
from simcore.topology import SimClient, SimDevice, Topology

#: Fraction of the radio PHY rate that turns into usable throughput.
WIRELESS_EFFICIENCY = 0.5

BUSY_THRESHOLD = 0.70
SATURATED_THRESHOLD = 0.95


@dataclass
class Demand:
    """One unidirectional stream the simulator has to place onto the topology."""

    id: str
    label: str
    kind: str  # client | flow
    source_id: str
    src_device: str
    dst_device: str
    mbps: float
    via_wan: bool = False
    wan_direction: str = "down"
    burstiness: float = 0.1
    protocol: str = "tcp"


@dataclass
class LinkLoad:
    link_id: str
    capacity_mbps: int
    a_to_b: float = 0.0
    b_to_a: float = 0.0
    offered_a_to_b: float = 0.0
    offered_b_to_a: float = 0.0
    storm: bool = False

    @property
    def load_mbps(self) -> float:
        return max(self.a_to_b, self.b_to_a)

    @property
    def utilisation(self) -> float:
        if self.storm:
            return 1.0
        return min(self.load_mbps / self.capacity_mbps, 1.0) if self.capacity_mbps else 0.0

    @property
    def offered_utilisation(self) -> float:
        if not self.capacity_mbps:
            return 0.0
        return max(self.offered_a_to_b, self.offered_b_to_a) / self.capacity_mbps

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "capacity_mbps": self.capacity_mbps,
            "a_to_b_mbps": round(self.a_to_b, 2),
            "b_to_a_mbps": round(self.b_to_a, 2),
            "load_mbps": round(self.load_mbps, 2),
            "utilisation": round(self.utilisation, 4),
            "offered_utilisation": round(self.offered_utilisation, 4),
            "storm": self.storm,
        }


@dataclass
class FlowResult:
    id: str
    label: str
    kind: str
    offered_mbps: float
    delivered_mbps: float
    path_device_ids: list[str]
    latency_ms: float
    bottleneck: str | None
    status: str  # ok | congested | dropped

    @property
    def loss_pct(self) -> float:
        if self.offered_mbps <= 0:
            return 0.0
        return max(0.0, 1 - self.delivered_mbps / self.offered_mbps) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "offered_mbps": round(self.offered_mbps, 2),
            "delivered_mbps": round(self.delivered_mbps, 2),
            "loss_pct": round(self.loss_pct, 2),
            "path_device_ids": self.path_device_ids,
            "latency_ms": round(self.latency_ms, 2),
            "bottleneck": self.bottleneck,
            "status": self.status,
        }


@dataclass
class TrafficResult:
    links: dict[str, LinkLoad]
    flows: list[FlowResult]
    device_throughput: dict[str, float]
    port_load: dict[str, float]
    wireless: dict[str, dict[str, float]]
    wan: dict[str, Any]
    history: list[dict[str, float]]
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "links": {k: v.to_dict() for k, v in self.links.items()},
            "flows": [f.to_dict() for f in self.flows],
            "device_throughput": {
                k: round(v, 2) for k, v in self.device_throughput.items()
            },
            "port_load": {k: round(v, 2) for k, v in self.port_load.items()},
            "wireless": self.wireless,
            "wan": self.wan,
            "history": self.history,
        }


def compute(topo: Topology, stp: StpResult, t: float = 0.0) -> TrafficResult:
    site = topo.site
    gateway = _pick_gateway(topo)
    demands = _collect_demands(topo, gateway, t)

    links = {
        link_id: LinkLoad(
            link_id=link_id, capacity_mbps=topo.negotiated_speed(topo.links[link_id])
        )
        for link_id in stp.active_link_ids
        if topo.is_l2_link(topo.links[link_id])
    }
    wan_caps = {"down": site.wan_download_mbps, "up": site.wan_upload_mbps}
    wan_offered = {"down": 0.0, "up": 0.0}

    adjacency = _adjacency(topo, stp)
    paths: dict[str, list[tuple[str, str]] | None] = {}
    device_paths: dict[str, list[str]] = {}

    for demand in demands:
        hops = _path(adjacency, demand.src_device, demand.dst_device)
        if hops is None:
            paths[demand.id] = None
            device_paths[demand.id] = []
            continue
        device_paths[demand.id] = hops
        segments = [
            (link_id, direction)
            for link_id, direction in _hop_links(adjacency, hops)
        ]
        if demand.via_wan:
            segments.insert(0, ("wan", demand.wan_direction))
        paths[demand.id] = segments
        for link_id, direction in segments:
            if link_id == "wan":
                wan_offered[direction] += demand.mbps
            elif link_id in links:
                load = links[link_id]
                if direction == "a_to_b":
                    load.offered_a_to_b += demand.mbps
                else:
                    load.offered_b_to_a += demand.mbps

    # Fair-share back-off: a demand is limited by the worst link on its path.
    def headroom(link_id: str, direction: str) -> float:
        if link_id == "wan":
            cap = wan_caps[direction]
            offered = wan_offered[direction]
        elif link_id in links:
            load = links[link_id]
            cap = float(load.capacity_mbps)
            offered = load.offered_a_to_b if direction == "a_to_b" else load.offered_b_to_a
        else:
            return 1.0
        if offered <= cap or offered == 0:
            return 1.0
        return cap / offered

    flows: list[FlowResult] = []
    wan_delivered = {"down": 0.0, "up": 0.0}
    device_throughput: dict[str, float] = {}
    port_load: dict[str, float] = {}

    for demand in demands:
        placed = paths[demand.id]
        if placed is None:
            flows.append(
                FlowResult(
                    id=demand.id,
                    label=demand.label,
                    kind=demand.kind,
                    offered_mbps=demand.mbps,
                    delivered_mbps=0.0,
                    path_device_ids=[],
                    latency_ms=0.0,
                    bottleneck=None,
                    status="dropped",
                )
            )
            continue
        ratios = [(headroom(lid, d), lid) for lid, d in placed] or [(1.0, "")]
        scale, bottleneck_id = min(ratios, key=lambda item: item[0])
        delivered = demand.mbps * scale
        for link_id, direction in placed:
            if link_id == "wan":
                wan_delivered[direction] += delivered
            elif link_id in links:
                load = links[link_id]
                if direction == "a_to_b":
                    load.a_to_b += delivered
                else:
                    load.b_to_a += delivered
        for device_id in device_paths[demand.id]:
            device_throughput[device_id] = device_throughput.get(device_id, 0.0) + delivered
        flows.append(
            FlowResult(
                id=demand.id,
                label=demand.label,
                kind=demand.kind,
                offered_mbps=demand.mbps,
                delivered_mbps=delivered,
                path_device_ids=device_paths[demand.id],
                latency_ms=_latency(placed, links, demand),
                bottleneck=bottleneck_id if scale < 1 else None,
                status="ok" if scale > 0.999 else "congested",
            )
        )

    _apply_storms(topo, stp, links)
    _accumulate_port_load(topo, demands, port_load)

    wireless = _wireless_usage(topo)
    wan = {
        "download_mbps": round(wan_delivered["down"], 2),
        "upload_mbps": round(wan_delivered["up"], 2),
        "download_capacity_mbps": wan_caps["down"],
        "upload_capacity_mbps": wan_caps["up"],
        "download_utilisation": round(
            min(wan_delivered["down"] / wan_caps["down"], 1.0) if wan_caps["down"] else 0.0, 4
        ),
        "upload_utilisation": round(
            min(wan_delivered["up"] / wan_caps["up"], 1.0) if wan_caps["up"] else 0.0, 4
        ),
        "gateway_id": gateway.id if gateway else None,
    }
    result = TrafficResult(
        links=links,
        flows=flows,
        device_throughput=device_throughput,
        port_load=port_load,
        wireless=wireless,
        wan=wan,
        history=_history(topo, gateway, t),
    )
    result.issues = _diagnose(topo, result, stp)
    return result


# ------------------------------------------------------------------- internals
def _pick_gateway(topo: Topology) -> SimDevice | None:
    for device in topo.site.devices:
        if not device.spec.routing or not device.enabled:
            continue
        if any(p.is_wan and p.enabled for p in device.ports):
            return device
    return None


def _jitter(seed: str, t: float, burstiness: float) -> float:
    """Deterministic per-stream variation. Seeded by name so that two copies of
    the same blueprint behave identically."""
    h = (zlib.crc32(seed.encode()) % 997) / 997 * math.tau
    wave = 0.6 * math.sin(t * 0.9 + h) + 0.4 * math.sin(t * 0.37 + h * 1.7)
    return max(0.0, 1.0 + burstiness * wave)


def _collect_demands(
    topo: Topology, gateway: SimDevice | None, t: float
) -> list[Demand]:
    demands: list[Demand] = []
    for client in topo.site.clients:
        anchor = _client_device(topo, client)
        if anchor is None or gateway is None:
            continue
        if client.down_mbps > 0:
            demands.append(
                Demand(
                    id=f"client:{client.id}:down",
                    label=f"{client.name} download",
                    kind="client",
                    source_id=client.id,
                    src_device=gateway.id,
                    dst_device=anchor,
                    mbps=client.down_mbps * _jitter(client.name + "|down", t, 0.35),
                    via_wan=True,
                    wan_direction="down",
                )
            )
        if client.up_mbps > 0:
            demands.append(
                Demand(
                    id=f"client:{client.id}:up",
                    label=f"{client.name} upload",
                    kind="client",
                    source_id=client.id,
                    src_device=anchor,
                    dst_device=gateway.id,
                    mbps=client.up_mbps * _jitter(client.name + "|up", t, 0.35),
                    via_wan=True,
                    wan_direction="up",
                )
            )
    for flow in topo.site.flows:
        if not flow.enabled:
            continue
        src = _endpoint_device(topo, flow.src_kind, flow.src_id, gateway)
        dst = _endpoint_device(topo, flow.dst_kind, flow.dst_id, gateway)
        if src is None or dst is None:
            continue
        rate = flow.mbps * _jitter(flow.name, t, flow.burstiness)
        via_wan = "internet" in (flow.src_kind, flow.dst_kind)
        demands.append(
            Demand(
                id=f"flow:{flow.id}",
                label=flow.name,
                kind="flow",
                source_id=flow.id,
                src_device=src,
                dst_device=dst,
                mbps=rate,
                via_wan=via_wan,
                wan_direction="down" if flow.src_kind == "internet" else "up",
                burstiness=flow.burstiness,
                protocol=flow.protocol,
            )
        )
        if flow.protocol == "tcp":
            demands.append(
                Demand(
                    id=f"flow:{flow.id}:ack",
                    label=f"{flow.name} (acks)",
                    kind="flow-ack",
                    source_id=flow.id,
                    src_device=dst,
                    dst_device=src,
                    mbps=rate * 0.04,
                    via_wan=via_wan,
                    wan_direction="up" if flow.src_kind == "internet" else "down",
                )
            )
    return demands


def _client_device(topo: Topology, client: SimClient) -> str | None:
    if client.kind == "wireless" and client.ap_id:
        device = topo.devices.get(client.ap_id)
        return device.id if device and device.enabled else None
    if client.port_id and client.port_id in topo.ports:
        device = topo.devices[topo.ports[client.port_id].device_id]
        port = topo.ports[client.port_id]
        return device.id if device.enabled and port.enabled else None
    return None


def _endpoint_device(
    topo: Topology, kind: str, ref: str, gateway: SimDevice | None
) -> str | None:
    if kind == "internet":
        return gateway.id if gateway else None
    if kind == "client":
        client = topo.clients.get(ref)
        return _client_device(topo, client) if client else None
    device = topo.devices.get(ref)
    return device.id if device and device.enabled else None


def _adjacency(
    topo: Topology, stp: StpResult
) -> dict[str, list[tuple[str, str, str]]]:
    """device -> [(neighbour, link_id, direction_from_this_device)]"""
    adjacency: dict[str, list[tuple[str, str, str]]] = {}
    for link_id in sorted(stp.active_link_ids):
        link = topo.links[link_id]
        if not topo.is_l2_link(link):
            continue
        a = topo.ports[link.a].device_id
        b = topo.ports[link.b].device_id
        if a == b:
            continue
        adjacency.setdefault(a, []).append((b, link_id, "a_to_b"))
        adjacency.setdefault(b, []).append((a, link_id, "b_to_a"))
    return adjacency


def _path(
    adjacency: dict[str, list[tuple[str, str, str]]], src: str, dst: str
) -> list[str] | None:
    if src == dst:
        return [src]
    previous: dict[str, str] = {src: src}
    queue: deque[str] = deque([src])
    while queue:
        node = queue.popleft()
        for neighbour, _link_id, _direction in adjacency.get(node, ()):
            if neighbour in previous:
                continue
            previous[neighbour] = node
            if neighbour == dst:
                walk = [dst]
                while walk[-1] != src:
                    walk.append(previous[walk[-1]])
                return list(reversed(walk))
            queue.append(neighbour)
    return None


def _hop_links(
    adjacency: dict[str, list[tuple[str, str, str]]], hops: list[str]
) -> Iterable[tuple[str, str]]:
    for current, nxt in pairwise(hops):
        for neighbour, link_id, direction in adjacency.get(current, ()):
            if neighbour == nxt:
                yield link_id, direction
                break


def _latency(
    segments: list[tuple[str, str]], links: dict[str, LinkLoad], demand: Demand
) -> float:
    latency = 0.0
    for link_id, _direction in segments:
        if link_id == "wan":
            latency += 8.0
            continue
        load = links.get(link_id)
        if load is None:
            continue
        latency += 0.06  # store-and-forward through one switch
        util = min(load.offered_utilisation, 0.999)
        latency += 12.0 * util**4  # queuing delay bites near the top of the pipe
    return latency


def _apply_storms(topo: Topology, stp: StpResult, links: dict[str, LinkLoad]) -> None:
    """Links inside a live loop are pegged by the broadcast storm."""
    looped_devices = {device_id for cycle in stp.loops for device_id in cycle}
    if not looped_devices:
        return
    for link_id, load in links.items():
        link = topo.links[link_id]
        a = topo.ports[link.a].device_id
        b = topo.ports[link.b].device_id
        if a in looped_devices and b in looped_devices:
            load.storm = True
            load.a_to_b = float(load.capacity_mbps)
            load.b_to_a = float(load.capacity_mbps)


def _accumulate_port_load(
    topo: Topology, demands: list[Demand], port_load: dict[str, float]
) -> None:
    for client in topo.site.clients:
        if client.port_id:
            port_load[client.port_id] = (
                port_load.get(client.port_id, 0.0) + client.down_mbps + client.up_mbps
            )


def _wireless_usage(topo: Topology) -> dict[str, dict[str, float]]:
    usage: dict[str, dict[str, float]] = {}
    for device in topo.site.devices:
        if not device.spec.wireless:
            continue
        clients = topo.clients_of_ap(device.id)
        demand = sum(c.down_mbps + c.up_mbps for c in clients)
        capacity = device.spec.wireless_capacity_mbps * WIRELESS_EFFICIENCY
        usage[device.id] = {
            "client_count": len(clients),
            "demand_mbps": round(demand, 2),
            "capacity_mbps": round(capacity, 2),
            "utilisation": round(min(demand / capacity, 1.0) if capacity else 0.0, 4),
        }
    return usage


def _history(
    topo: Topology, gateway: SimDevice | None, t: float, samples: int = 60
) -> list[dict[str, float]]:
    down_base = sum(c.down_mbps for c in topo.site.clients)
    up_base = sum(c.up_mbps for c in topo.site.clients)
    for flow in topo.site.flows:
        if not flow.enabled:
            continue
        if flow.src_kind == "internet":
            down_base += flow.mbps
        elif flow.dst_kind == "internet":
            up_base += flow.mbps
    cap_down = topo.site.wan_download_mbps
    cap_up = topo.site.wan_upload_mbps
    history = []
    for step in range(samples):
        moment = t - (samples - 1 - step)
        history.append(
            {
                "t": round(moment, 1),
                "download_mbps": round(
                    min(down_base * _jitter("wan-down", moment, 0.3), cap_down), 2
                ),
                "upload_mbps": round(
                    min(up_base * _jitter("wan-up", moment, 0.3), cap_up), 2
                ),
            }
        )
    return history


def _diagnose(topo: Topology, result: TrafficResult, stp: StpResult) -> list[Issue]:
    issues: list[Issue] = []
    for link_id, load in sorted(result.links.items()):
        link = topo.links[link_id]
        a_port, b_port = topo.ports[link.a], topo.ports[link.b]
        a_dev, b_dev = topo.devices[a_port.device_id], topo.devices[b_port.device_id]
        label = f"{a_dev.name} {a_port.label} → {b_dev.name} {b_port.label}"
        subjects = (
            Subject("link", link_id, label),
            Subject("device", a_dev.id, a_dev.name),
            Subject("device", b_dev.id, b_dev.name),
        )
        if load.storm:
            issues.append(
                Issue(
                    code="capacity.broadcast_storm",
                    severity=Severity.CRITICAL,
                    category="capacity",
                    title=f"Broadcast storm on {label}",
                    detail=(
                        "This link is inside a forwarding loop. Looped broadcast traffic "
                        "has consumed the whole link and normal traffic will not get through."
                    ),
                    recommendation="Break the loop, then the storm clears on its own.",
                    subjects=subjects,
                )
            )
        elif load.offered_utilisation >= SATURATED_THRESHOLD:
            issues.append(
                Issue(
                    code="capacity.link_saturated",
                    severity=Severity.WARNING,
                    category="capacity",
                    title=f"{label} is saturated",
                    detail=(
                        f"{load.load_mbps:.0f} Mbps of offered traffic on a "
                        f"{load.capacity_mbps} Mbps link "
                        f"({load.offered_utilisation * 100:.0f}% of capacity)."
                    ),
                    recommendation=(
                        "Move to a faster port, add a second uplink, or shift clients "
                        "to another switch."
                    ),
                    subjects=subjects,
                    meta={"utilisation": round(load.offered_utilisation, 3)},
                )
            )
        elif load.offered_utilisation >= BUSY_THRESHOLD:
            issues.append(
                Issue(
                    code="capacity.link_busy",
                    severity=Severity.INFO,
                    category="capacity",
                    title=f"{label} is running at {load.offered_utilisation * 100:.0f}%",
                    detail="Sustained load above 70% leaves little burst headroom.",
                    recommendation="Keep an eye on it before adding more clients.",
                    subjects=subjects,
                )
            )

    for flow in result.flows:
        if flow.status == "dropped" and flow.kind != "flow-ack":
            issues.append(
                Issue(
                    code="traffic.no_path",
                    severity=Severity.WARNING,
                    category="capacity",
                    title=f"{flow.label} has nowhere to go",
                    detail=(
                        "There is no forwarding path between the two endpoints. Either "
                        "a cable is missing, a port is blocked, or the device is offline."
                    ),
                    recommendation="Check the path between the endpoints in Topology.",
                    subjects=(Subject("flow", flow.id, flow.label),),
                )
            )

    for device_id, usage in sorted(result.wireless.items()):
        if usage["utilisation"] >= 0.85 and usage["client_count"]:
            device = topo.devices[device_id]
            issues.append(
                Issue(
                    code="capacity.wireless_saturated",
                    severity=Severity.WARNING,
                    category="capacity",
                    title=f"{device.name} radio is at {usage['utilisation'] * 100:.0f}%",
                    detail=(
                        f"{usage['client_count']} wireless clients are asking for "
                        f"{usage['demand_mbps']:.0f} Mbps against about "
                        f"{usage['capacity_mbps']:.0f} Mbps of usable airtime."
                    ),
                    recommendation="Add another access point or move clients to 5/6 GHz.",
                    subjects=(Subject("device", device.id, device.name),),
                )
            )

    wan = result.wan
    for direction in ("download", "upload"):
        if wan[f"{direction}_utilisation"] < SATURATED_THRESHOLD:
            continue
        issues.append(
            Issue(
                code=f"capacity.wan_{direction}_saturated",
                severity=Severity.WARNING,
                category="capacity",
                title=f"Internet {direction} is saturated",
                detail=(
                    f"{wan[f'{direction}_mbps']:.0f} Mbps of "
                    f"{wan[f'{direction}_capacity_mbps']:.0f} Mbps is in use, so traffic "
                    "to the internet is being queued."
                ),
                recommendation=(
                    "Raise the WAN speed on the site, or shape the busiest clients."
                ),
                subjects=(Subject("site", topo.site.id, topo.site.name),),
            )
        )
    return issues
