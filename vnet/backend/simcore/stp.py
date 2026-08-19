"""Spanning tree simulation (802.1D / 802.1w).

The model is a single-instance spanning tree, which is what UniFi runs by
default. Devices that cannot run STP — access points, cameras, unmanaged gear,
or a switch where the user turned STP off — are treated as hubs: every cable
plugged into them is merged into one shared segment. That is what makes the
classic "someone patched two wall ports together" loop show up here exactly as
it would on real hardware.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from simcore.issues import Issue, Severity, Subject
from simcore.topology import SimDevice, SimLink, Topology

#: IEEE 802.1D-2004 recommended path costs, keyed by link speed in Mbps.
PATH_COST = {
    10: 2_000_000,
    100: 200_000,
    1000: 20_000,
    2500: 8_000,
    5000: 4_000,
    10000: 2_000,
    25000: 800,
    40000: 500,
}

ROLE_ROOT = "root"
ROLE_DESIGNATED = "designated"
ROLE_ALTERNATE = "alternate"
ROLE_BACKUP = "backup"
ROLE_DISABLED = "disabled"


def path_cost(speed_mbps: int) -> int:
    if speed_mbps in PATH_COST:
        return PATH_COST[speed_mbps]
    # Fall back to the nearest defined rate at or below the negotiated speed.
    candidates = [s for s in PATH_COST if s <= speed_mbps]
    return PATH_COST[max(candidates)] if candidates else PATH_COST[10]


@dataclass
class Segment:
    """One shared collision/broadcast domain (a cable, or a hub's worth of them)."""

    id: str
    link_ids: set[str] = field(default_factory=set)
    bridge_port_ids: list[str] = field(default_factory=list)
    hub_device_ids: list[str] = field(default_factory=list)
    designated_port_id: str | None = None
    root_cost: int = 0


@dataclass
class PortStp:
    port_id: str
    device_id: str
    role: str
    state: str  # forwarding | discarding | disabled | err-disabled
    cost: int = 0
    root_path_cost: int = 0
    edge: bool = False
    segment_id: str | None = None
    reason: str = ""

    @property
    def blocked(self) -> bool:
        return self.state in ("discarding", "err-disabled")

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "device_id": self.device_id,
            "role": self.role,
            "state": self.state,
            "cost": self.cost,
            "root_path_cost": self.root_path_cost,
            "edge": self.edge,
            "segment_id": self.segment_id,
            "reason": self.reason,
        }


@dataclass
class BridgeStp:
    device_id: str
    priority: int
    mac: str
    is_root: bool
    root_device_id: str
    root_path_cost: int
    root_port_id: str | None
    component: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "priority": self.priority,
            "bridge_id": f"{self.priority}.{self.mac}",
            "is_root": self.is_root,
            "root_device_id": self.root_device_id,
            "root_path_cost": self.root_path_cost,
            "root_port_id": self.root_port_id,
            "component": self.component,
        }


@dataclass
class StpResult:
    mode: str
    bridges: dict[str, BridgeStp]
    ports: dict[str, PortStp]
    segments: list[Segment]
    root_device_ids: list[str]
    active_link_ids: set[str]
    blocked_link_ids: set[str]
    down_link_ids: set[str]
    loops: list[list[str]]
    issues: list[Issue]
    convergence_estimate_s: float

    def port_state(self, port_id: str) -> str:
        entry = self.ports.get(port_id)
        return entry.state if entry else "forwarding"

    def link_state(self, link_id: str) -> str:
        if link_id in self.down_link_ids:
            return "down"
        if link_id in self.blocked_link_ids:
            return "blocked"
        return "forwarding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "root_device_ids": self.root_device_ids,
            "convergence_estimate_s": self.convergence_estimate_s,
            "bridges": {k: v.to_dict() for k, v in self.bridges.items()},
            "ports": {k: v.to_dict() for k, v in self.ports.items()},
            "segments": [
                {
                    "id": s.id,
                    "link_ids": sorted(s.link_ids),
                    "bridge_port_ids": s.bridge_port_ids,
                    "hub_device_ids": s.hub_device_ids,
                    "designated_port_id": s.designated_port_id,
                    "root_cost": s.root_cost,
                }
                for s in self.segments
            ],
            "loops": self.loops,
            "active_link_ids": sorted(self.active_link_ids),
            "blocked_link_ids": sorted(self.blocked_link_ids),
            "down_link_ids": sorted(self.down_link_ids),
        }


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[rb] = ra
        return True


def compute(topo: Topology) -> StpResult:
    site = topo.site
    issues: list[Issue] = []
    port_states: dict[str, PortStp] = {}

    err_disabled = _apply_bpdu_guard(topo, issues, port_states)

    up_l2_links = [
        link
        for link in site.links
        if topo.is_l2_link(link)
        and topo.link_up(link)
        and link.a not in err_disabled
        and link.b not in err_disabled
    ]
    down_link_ids = {
        link.id
        for link in site.links
        if link.id not in {up.id for up in up_l2_links} and topo.is_l2_link(link)
    }

    segments = _build_segments(topo, up_l2_links)
    bridges = _run_spanning_tree(topo, segments, port_states)
    _mark_leftover_ports(topo, port_states, err_disabled)

    active_link_ids, blocked_link_ids = _classify_links(topo, up_l2_links, port_states)
    loops = _find_loops(topo, active_link_ids)

    root_device_ids = sorted({b.root_device_id for b in bridges.values()})
    result = StpResult(
        mode=site.stp_mode,
        bridges=bridges,
        ports=port_states,
        segments=segments,
        root_device_ids=root_device_ids,
        active_link_ids=active_link_ids,
        blocked_link_ids=blocked_link_ids,
        down_link_ids=down_link_ids,
        loops=loops,
        issues=issues,
        convergence_estimate_s=_convergence_estimate(site.stp_mode, bridges),
    )
    issues.extend(_diagnose(topo, result))
    return result


# --------------------------------------------------------------------- stages
def _apply_bpdu_guard(
    topo: Topology, issues: list[Issue], port_states: dict[str, PortStp]
) -> set[str]:
    """Shut down guarded ports that can see another bridge, like real hardware."""
    err_disabled: set[str] = set()
    for port in topo.ports.values():
        if not port.bpdu_guard:
            continue
        link = topo.link_of(port.id)
        if link is None or not topo.link_up(link):
            continue
        peer = topo.peer_port(port.id)
        if peer is None:
            continue
        peer_device = topo.devices[peer.device_id]
        if not topo.is_bridge(peer_device) and not peer_device.spec.stp_capable:
            continue
        err_disabled.add(port.id)
        device = topo.devices[port.device_id]
        port_states[port.id] = PortStp(
            port_id=port.id,
            device_id=port.device_id,
            role=ROLE_DISABLED,
            state="err-disabled",
            reason="BPDU guard triggered",
        )
        issues.append(
            Issue(
                code="stp.bpdu_guard_violation",
                severity=Severity.CRITICAL,
                category="stp",
                title=f"BPDU guard shut down {device.name} {port.label}",
                detail=(
                    f"{port.label} is configured as an edge port with BPDU guard, but "
                    f"{peer_device.name} is a bridge and sent BPDUs on it. The port has "
                    "been err-disabled and no longer passes traffic."
                ),
                recommendation=(
                    "Either unplug the switch from this port, or clear BPDU guard on it "
                    "if this uplink is intentional."
                ),
                subjects=(
                    Subject("device", device.id, device.name),
                    Subject("port", port.id, f"{device.name} {port.label}"),
                ),
            )
        )
    return err_disabled


def _build_segments(topo: Topology, links: list[SimLink]) -> list[Segment]:
    """Merge cables that share a non-STP forwarding device into one segment."""
    uf = _UnionFind()
    for link in links:
        uf.add(link.id)

    hub_devices: dict[str, list[str]] = {}
    for device in topo.site.devices:
        if not device.enabled or topo.is_bridge(device) or not device.forwards_frames:
            continue
        attached = [item.id for item in links if _touches(topo, item, device.id)]
        if not attached:
            continue
        hub_devices[device.id] = attached
        first = attached[0]
        for other in attached[1:]:
            uf.union(first, other)

    grouped: dict[str, Segment] = {}
    for link in links:
        root = uf.find(link.id)
        seg = grouped.setdefault(root, Segment(id=f"seg-{root}"))
        seg.link_ids.add(link.id)

    for device_id, attached in hub_devices.items():
        seg = grouped[uf.find(attached[0])]
        seg.hub_device_ids.append(device_id)

    for seg in grouped.values():
        seen: list[str] = []
        for link_id in sorted(seg.link_ids):
            link = topo.links[link_id]
            for port_id in (link.a, link.b):
                device = topo.device_of(port_id)
                if topo.is_bridge(device) and port_id not in seen:
                    seen.append(port_id)
        seg.bridge_port_ids = seen
    return sorted(grouped.values(), key=lambda s: s.id)


def _touches(topo: Topology, link: SimLink, device_id: str) -> bool:
    return (
        topo.ports[link.a].device_id == device_id
        or topo.ports[link.b].device_id == device_id
    )


def _run_spanning_tree(
    topo: Topology, segments: list[Segment], port_states: dict[str, PortStp]
) -> dict[str, BridgeStp]:
    bridges = [d for d in topo.site.devices if topo.is_bridge(d)]
    if not bridges:
        return {}

    seg_by_id = {s.id: s for s in segments}
    ports_of_bridge: dict[str, list[tuple[str, str]]] = {d.id: [] for d in bridges}
    seg_of_port: dict[str, str] = {}
    for seg in segments:
        for port_id in seg.bridge_port_ids:
            device_id = topo.ports[port_id].device_id
            ports_of_bridge.setdefault(device_id, []).append((port_id, seg.id))
            seg_of_port[port_id] = seg.id

    cost_of_port = {
        port_id: _port_cost(topo, port_id) for port_id in seg_of_port
    }

    # Group bridges into connected components so each island elects its own root.
    uf = _UnionFind()
    for device in bridges:
        uf.add(device.id)
    for seg in segments:
        device_ids = [topo.ports[p].device_id for p in seg.bridge_port_ids]
        for other in device_ids[1:]:
            uf.union(device_ids[0], other)

    components: dict[str, list[SimDevice]] = {}
    for device in bridges:
        components.setdefault(uf.find(device.id), []).append(device)

    result: dict[str, BridgeStp] = {}
    for component_index, (_, members) in enumerate(sorted(components.items())):
        root = min(members, key=lambda d: d.bridge_id)
        dist: dict[str, int] = {root.id: 0}
        queue: list[tuple[int, str]] = [(0, root.id)]
        while queue:
            d, device_id = heapq.heappop(queue)
            if d > dist.get(device_id, 1 << 60):
                continue
            for _port_id, seg_id in ports_of_bridge.get(device_id, []):
                for peer_port_id in seg_by_id[seg_id].bridge_port_ids:
                    peer_device_id = topo.ports[peer_port_id].device_id
                    if peer_device_id == device_id:
                        continue
                    candidate = d + cost_of_port[peer_port_id]
                    if candidate < dist.get(peer_device_id, 1 << 60):
                        dist[peer_device_id] = candidate
                        heapq.heappush(queue, (candidate, peer_device_id))

        member_ids = {m.id for m in members}
        # Designated bridge/port per segment: lowest root cost, then lowest bridge ID.
        for seg in segments:
            if not seg.bridge_port_ids:
                continue
            if topo.ports[seg.bridge_port_ids[0]].device_id not in member_ids:
                continue
            best = min(
                seg.bridge_port_ids,
                key=lambda pid: (
                    dist.get(topo.ports[pid].device_id, 1 << 60),
                    topo.devices[topo.ports[pid].device_id].bridge_id,
                    topo.ports[pid].index,
                ),
            )
            seg.designated_port_id = best
            seg.root_cost = dist.get(topo.ports[best].device_id, 1 << 60)

        # Root port per non-root bridge.
        root_port: dict[str, str | None] = {root.id: None}
        for device in members:
            if device.id == root.id:
                continue
            # Best received BPDU wins: lowest root path cost, then the lowest
            # sender bridge ID, sender port and finally our own port number.
            candidates: list[tuple[tuple[int, tuple[int, str], int, int], str]] = []
            for port_id, seg_id in ports_of_bridge.get(device.id, []):
                designated_id = seg_by_id[seg_id].designated_port_id
                if designated_id is None:
                    continue
                designated = topo.ports[designated_id]
                if designated.device_id == device.id:
                    continue
                candidates.append(
                    (
                        (
                            seg_by_id[seg_id].root_cost + cost_of_port[port_id],
                            topo.devices[designated.device_id].bridge_id,
                            designated.index,
                            topo.ports[port_id].index,
                        ),
                        port_id,
                    )
                )
            root_port[device.id] = min(candidates)[1] if candidates else None

        for device in members:
            result[device.id] = BridgeStp(
                device_id=device.id,
                priority=device.stp_priority,
                mac=device.mac,
                is_root=device.id == root.id,
                root_device_id=root.id,
                root_path_cost=dist.get(device.id, 0),
                root_port_id=root_port.get(device.id),
                component=component_index,
            )

        # Assign a role and a state to every bridge port in this component.
        for seg in segments:
            if not seg.bridge_port_ids:
                continue
            if topo.ports[seg.bridge_port_ids[0]].device_id not in member_ids:
                continue
            is_edge = len(seg.bridge_port_ids) == 1 and not seg.hub_device_ids
            for port_id in seg.bridge_port_ids:
                device_id = topo.ports[port_id].device_id
                if port_id == seg.designated_port_id:
                    role, state, reason = ROLE_DESIGNATED, "forwarding", ""
                elif root_port.get(device_id) == port_id:
                    role, state, reason = ROLE_ROOT, "forwarding", ""
                elif (
                    seg.designated_port_id
                    and topo.ports[seg.designated_port_id].device_id == device_id
                ):
                    role = ROLE_BACKUP
                    state = "discarding"
                    reason = "Backup port for a segment this switch already serves"
                else:
                    role = ROLE_ALTERNATE
                    state = "discarding"
                    reason = "Alternate path to the root bridge — blocked to break a loop"
                port_states[port_id] = PortStp(
                    port_id=port_id,
                    device_id=device_id,
                    role=role,
                    state=state,
                    cost=cost_of_port[port_id],
                    root_path_cost=dist.get(device_id, 0),
                    edge=is_edge and role == ROLE_DESIGNATED,
                    segment_id=seg.id,
                    reason=reason,
                )
    return result


def _port_cost(topo: Topology, port_id: str) -> int:
    link = topo.link_of(port_id)
    speed = (
        topo.negotiated_speed(link)
        if link is not None
        else topo.ports[port_id].max_speed_mbps
    )
    return path_cost(speed)


def _mark_leftover_ports(
    topo: Topology, port_states: dict[str, PortStp], err_disabled: set[str]
) -> None:
    """Ports the spanning tree never saw: admin-down, unpatched, or plain edge."""
    for port in topo.ports.values():
        if port.id in port_states:
            continue
        device = topo.devices[port.device_id]
        if not port.enabled or not device.enabled:
            state, role = "disabled", ROLE_DISABLED
        else:
            state, role = "forwarding", ROLE_DESIGNATED
        port_states[port.id] = PortStp(
            port_id=port.id,
            device_id=port.device_id,
            role=role,
            state=state,
            cost=path_cost(port.max_speed_mbps),
            edge=state == "forwarding",
        )


def _classify_links(
    topo: Topology, up_links: list[SimLink], port_states: dict[str, PortStp]
) -> tuple[set[str], set[str]]:
    active: set[str] = set()
    blocked: set[str] = set()
    for link in up_links:
        states = [port_states[link.a].state, port_states[link.b].state]
        if all(s == "forwarding" for s in states):
            active.add(link.id)
        else:
            blocked.add(link.id)
    for link in topo.site.links:
        if not topo.is_l2_link(link) and topo.link_up(link):
            active.add(link.id)
    return active, blocked


def _find_loops(topo: Topology, active_link_ids: set[str]) -> list[list[str]]:
    """Cycles that survive spanning tree — these are live broadcast storms."""
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for link_id in sorted(active_link_ids):
        link = topo.links[link_id]
        if not topo.is_l2_link(link):
            continue
        a = topo.ports[link.a].device_id
        b = topo.ports[link.b].device_id
        adjacency.setdefault(a, []).append((b, link_id))
        adjacency.setdefault(b, []).append((a, link_id))

    loops: list[list[str]] = []
    seen_links: set[str] = set()
    # A cable patched from a device straight back into itself is its own loop.
    for link_id in sorted(active_link_ids):
        link = topo.links[link_id]
        if not topo.is_l2_link(link):
            continue
        if topo.ports[link.a].device_id == topo.ports[link.b].device_id:
            loops.append([topo.ports[link.a].device_id])
            seen_links.add(link_id)

    visited: set[str] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        parent_link: dict[str, str | None] = {start: None}
        parent: dict[str, str | None] = {start: None}
        stack = [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            for neighbour, link_id in adjacency[node]:
                if link_id == parent_link.get(node) or link_id in seen_links:
                    continue
                if neighbour not in visited:
                    visited.add(neighbour)
                    parent[neighbour] = node
                    parent_link[neighbour] = link_id
                    stack.append(neighbour)
                else:
                    seen_links.add(link_id)
                    loops.append(_cycle_path(parent, node, neighbour))
    return loops


def _cycle_path(
    parent: dict[str, str | None], a: str, b: str
) -> list[str]:
    """Walk both nodes up to their common ancestor to describe the loop."""
    seen_a = []
    node: str | None = a
    while node is not None:
        seen_a.append(node)
        node = parent.get(node)
    seen_b = []
    node = b
    while node is not None and node not in seen_a:
        seen_b.append(node)
        node = parent.get(node)
    if node is None:
        return list(dict.fromkeys(seen_a + seen_b))
    head = seen_a[: seen_a.index(node) + 1]
    return list(dict.fromkeys(head + list(reversed(seen_b))))


def _convergence_estimate(mode: str, bridges: dict[str, BridgeStp]) -> float:
    if mode == "disabled" or not bridges:
        return 0.0
    depth = max((b.root_path_cost for b in bridges.values()), default=0)
    hops = max(1, depth // 20000 + 1)
    if mode == "stp":
        return round(30.0 + 2.0 * hops, 1)  # max age + 2x forward delay
    return round(min(1.0 + 0.6 * hops, 6.0), 1)  # RSTP proposal/agreement


# ------------------------------------------------------------------ diagnostics
def _diagnose(topo: Topology, result: StpResult) -> list[Issue]:
    issues: list[Issue] = []
    site = topo.site

    for cycle in result.loops:
        names = [topo.devices[d].name for d in cycle if d in topo.devices]
        path = " → ".join(names + names[:1]) if names else "unknown"
        issues.append(
            Issue(
                code="stp.loop_active",
                severity=Severity.CRITICAL,
                category="stp",
                title="Forwarding loop detected",
                detail=(
                    f"Frames can circulate forever around {path}. Nothing in this path "
                    "is running spanning tree, so no port will block and broadcast "
                    "traffic will saturate every link in the loop."
                ),
                recommendation=(
                    "Remove one of the cables in the loop, or replace the unmanaged "
                    "device in the path with a UniFi switch so STP can block a port."
                ),
                subjects=tuple(
                    Subject("device", d, topo.devices[d].name)
                    for d in cycle
                    if d in topo.devices
                ),
                meta={"cycle": cycle},
            )
        )

    if site.stp_mode == "disabled":
        physical_cycles = _physical_cycle_count(topo)
        if physical_cycles:
            issues.append(
                Issue(
                    code="stp.disabled_with_redundancy",
                    severity=Severity.CRITICAL,
                    category="stp",
                    title="Spanning tree is turned off and the topology has a loop",
                    detail=(
                        f"{physical_cycles} redundant path(s) exist but STP is disabled "
                        "site-wide, so no port can block."
                    ),
                    recommendation="Set the site spanning tree mode to RSTP.",
                    subjects=(Subject("site", site.id, site.name),),
                )
            )
    elif site.stp_mode == "stp":
        issues.append(
            Issue(
                code="stp.legacy_mode",
                severity=Severity.INFO,
                category="stp",
                title="Site is running legacy 802.1D spanning tree",
                detail=(
                    "Convergence after a link failure takes around "
                    f"{result.convergence_estimate_s:.0f} s. RSTP recovers in seconds."
                ),
                recommendation="Switch the site to RSTP unless legacy gear requires 802.1D.",
                subjects=(Subject("site", site.id, site.name),),
            )
        )

    for port_id, state in sorted(result.ports.items()):
        if state.role not in (ROLE_ALTERNATE, ROLE_BACKUP):
            continue
        port = topo.ports[port_id]
        device = topo.devices[port.device_id]
        peer = topo.peer_port(port_id)
        peer_label = (
            f"{topo.devices[peer.device_id].name} {peer.label}" if peer else "segment"
        )
        issues.append(
            Issue(
                code="stp.port_blocked",
                severity=Severity.INFO,
                category="stp",
                title=f"{device.name} {port.label} is blocking",
                detail=(
                    f"Spanning tree put this port into discarding to keep the path to "
                    f"{peer_label} loop-free. The link is standing by and will take over "
                    f"in about {result.convergence_estimate_s:.0f} s if the active path fails."
                ),
                recommendation="",
                subjects=(
                    Subject("device", device.id, device.name),
                    Subject("port", port_id, f"{device.name} {port.label}"),
                ),
            )
        )

    issues.extend(_diagnose_root(topo, result))
    issues.extend(_diagnose_partitions(topo, result))
    issues.extend(_diagnose_hubs(topo, result))
    return issues


def _diagnose_root(topo: Topology, result: StpResult) -> list[Issue]:
    issues: list[Issue] = []
    for root_id in result.root_device_ids:
        root = topo.devices.get(root_id)
        if root is None:
            continue
        peers = [b for b in result.bridges.values() if b.root_device_id == root_id]
        if len(peers) < 2:
            continue
        if root.line not in ("gateway",) and any(
            topo.devices[b.device_id].line == "gateway" for b in peers
        ):
            gateway = next(
                topo.devices[b.device_id]
                for b in peers
                if topo.devices[b.device_id].line == "gateway"
            )
            issues.append(
                Issue(
                    code="stp.root_not_core",
                    severity=Severity.WARNING,
                    category="stp",
                    title=f"{root.name} won the root bridge election",
                    detail=(
                        f"The root bridge is an access-layer device. {gateway.name} sits "
                        "at the core of this network, so traffic between switches may be "
                        "taking a longer path than it needs to."
                    ),
                    recommendation=(
                        f"Set {gateway.name}'s STP priority to 4096 so it becomes root."
                    ),
                    subjects=(
                        Subject("device", root.id, root.name),
                        Subject("device", gateway.id, gateway.name),
                    ),
                )
            )
        tied = [
            b
            for b in peers
            if b.priority == min(p.priority for p in peers)
        ]
        if len(tied) > 1:
            names = ", ".join(sorted(topo.devices[b.device_id].name for b in tied))
            issues.append(
                Issue(
                    code="stp.priority_tie",
                    severity=Severity.WARNING,
                    category="stp",
                    title="Root bridge is being decided by MAC address",
                    detail=(
                        f"{names} all share STP priority {tied[0].priority}, so the root "
                        "election falls back to the lowest MAC address. Swapping hardware "
                        "can silently move the root of your network."
                    ),
                    recommendation=(
                        "Give the device you want as root a lower priority (for example 4096)."
                    ),
                    subjects=tuple(
                        Subject("device", b.device_id, topo.devices[b.device_id].name)
                        for b in tied
                    ),
                )
            )
    return issues


def _diagnose_partitions(topo: Topology, result: StpResult) -> list[Issue]:
    gateways = topo.uplink_candidates()
    if not gateways:
        return [
            Issue(
                code="topology.no_gateway",
                severity=Severity.WARNING,
                category="topology",
                title="No gateway in this site",
                detail=(
                    "Nothing in the topology can route to the internet, so any flow "
                    "with an internet endpoint will be dropped."
                ),
                recommendation="Add a UniFi gateway or Dream Machine and cable it in.",
                subjects=(Subject("site", topo.site.id, topo.site.name),),
            )
        ]

    reachable = _reachable_devices(topo, result, {g.id for g in gateways})
    stranded = [
        d
        for d in topo.site.devices
        if d.enabled and d.id not in reachable and topo.links_of(d.id)
    ]
    unpatched = [
        d for d in topo.site.devices if d.enabled and not topo.links_of(d.id)
    ]
    issues: list[Issue] = []
    for device in stranded:
        issues.append(
            Issue(
                code="topology.isolated",
                severity=Severity.WARNING,
                category="topology",
                title=f"{device.name} cannot reach the gateway",
                detail=(
                    "This device is cabled, but every path to the gateway is down or "
                    "blocked, so it is cut off from the rest of the network."
                ),
                recommendation="Check the uplink cable and the port state along the path.",
                subjects=(Subject("device", device.id, device.name),),
            )
        )
    for device in unpatched:
        issues.append(
            Issue(
                code="topology.unpatched",
                severity=Severity.INFO,
                category="topology",
                title=f"{device.name} has no cables",
                detail="The device exists in the site but nothing is patched into it.",
                recommendation="Patch its uplink port into a switch.",
                subjects=(Subject("device", device.id, device.name),),
            )
        )
    return issues


def _diagnose_hubs(topo: Topology, result: StpResult) -> list[Issue]:
    issues: list[Issue] = []
    for seg in result.segments:
        for device_id in seg.hub_device_ids:
            device = topo.devices[device_id]
            if len(topo.links_of(device_id)) < 2:
                continue
            if device.spec.stp_capable and not device.stp_enabled:
                issues.append(
                    Issue(
                        code="stp.disabled_on_device",
                        severity=Severity.WARNING,
                        category="stp",
                        title=f"Spanning tree is off on {device.name}",
                        detail=(
                            "This switch forwards frames between several cables but does "
                            "not run STP, so it cannot block a port if a loop forms "
                            "through it."
                        ),
                        recommendation=f"Re-enable spanning tree on {device.name}.",
                        subjects=(Subject("device", device.id, device.name),),
                    )
                )
            elif device.line == "ap":
                issues.append(
                    Issue(
                        code="stp.daisy_chained_ap",
                        severity=Severity.INFO,
                        category="stp",
                        title=f"{device.name} is bridging traffic between cables",
                        detail=(
                            "An access point is carrying wired traffic for other devices. "
                            "It does not run spanning tree, so a second cable into this "
                            "chain would create a loop nothing can break."
                        ),
                        recommendation="Give the downstream device its own switch port.",
                        subjects=(Subject("device", device.id, device.name),),
                    )
                )
    return issues


def _reachable_devices(
    topo: Topology, result: StpResult, seeds: set[str]
) -> set[str]:
    adjacency: dict[str, set[str]] = {}
    for link_id in result.active_link_ids:
        link = topo.links[link_id]
        a, b = topo.ports[link.a].device_id, topo.ports[link.b].device_id
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    seen = set(seeds)
    stack = list(seeds)
    while stack:
        node = stack.pop()
        for neighbour in adjacency.get(node, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _physical_cycle_count(topo: Topology) -> int:
    uf = _UnionFind()
    cycles = 0
    for link in topo.site.links:
        if not topo.is_l2_link(link) or not topo.link_up(link):
            continue
        a, b = topo.ports[link.a].device_id, topo.ports[link.b].device_id
        if not uf.union(a, b):
            cycles += 1
    return cycles
