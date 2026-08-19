"""Top-level entry point: take a site, hand back everything the console draws."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from simcore import power as power_mod
from simcore import stp as stp_mod
from simcore import traffic as traffic_mod
from simcore.issues import Issue, Severity, Subject, sort_issues
from simcore.power import PowerResult
from simcore.stp import StpResult
from simcore.topology import SimSite, Topology
from simcore.traffic import TrafficResult


@dataclass
class SimulationResult:
    site: SimSite
    topology: Topology
    stp: StpResult
    power: PowerResult
    traffic: TrafficResult
    issues: list[Issue]
    t: float

    # ------------------------------------------------------------------ health
    @property
    def counts(self) -> dict[str, int]:
        by_severity = {"critical": 0, "warning": 0, "info": 0}
        for issue in self.issues:
            by_severity[issue.severity.value] += 1
        return by_severity

    @property
    def health_score(self) -> int:
        counts = self.counts
        score = 100 - counts["critical"] * 25 - counts["warning"] * 7 - counts["info"] * 1
        return max(0, min(100, score))

    @property
    def health_status(self) -> str:
        counts = self.counts
        if counts["critical"]:
            return "critical"
        if counts["warning"]:
            return "warning"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "site": {
                "id": self.site.id,
                "name": self.site.name,
                "stp_mode": self.site.stp_mode,
                "wan_download_mbps": self.site.wan_download_mbps,
                "wan_upload_mbps": self.site.wan_upload_mbps,
            },
            "health": {
                "score": self.health_score,
                "status": self.health_status,
                "counts": self.counts,
                "device_count": len(self.site.devices),
                "client_count": len(self.site.clients),
                "link_count": len(self.site.links),
                "convergence_estimate_s": self.stp.convergence_estimate_s,
            },
            "devices": self._devices(),
            "links": self._links(),
            "clients": self._clients(),
            "stp": self.stp.to_dict(),
            "power": self.power.to_dict(),
            "traffic": self.traffic.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
        }

    # ----------------------------------------------------------------- sections
    def _devices(self) -> list[dict[str, Any]]:
        topo = self.topology
        rows = []
        for device in self.site.devices:
            spec = device.spec
            bridge = self.stp.bridges.get(device.id)
            uplink = self._uplink_of(device.id)
            offline = device.id in self.power.offline_device_ids or not device.enabled
            pse = self.power.pse.get(device.id)
            rows.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "model": device.model,
                    "model_name": spec.name,
                    "short": spec.short,
                    "line": spec.line,
                    "mac": device.mac,
                    "ip": device.ip,
                    "x": device.x,
                    "y": device.y,
                    "status": self._device_status(device.id, offline),
                    "enabled": device.enabled,
                    "throughput_mbps": round(
                        self.traffic.device_throughput.get(device.id, 0.0), 2
                    ),
                    "client_count": len(topo.clients_of_ap(device.id))
                    + sum(
                        len(topo.clients_of_port(p.id)) for p in device.ports
                    ),
                    "power_draw_w": spec.power_draw_w,
                    "poe_used_w": round(pse.used_w, 1) if pse else 0.0,
                    "poe_budget_w": spec.poe_budget_w,
                    "uplink_device_id": uplink[0],
                    "uplink_port_id": uplink[1],
                    "uplink_kind": "internet"
                    if spec.routing and uplink[0] is None and uplink[1]
                    else ("device" if uplink[0] else "none"),
                    "stp": bridge.to_dict() if bridge else None,
                    "stp_enabled": device.stp_enabled,
                    "stp_priority": device.stp_priority,
                    "wireless": self.traffic.wireless.get(device.id),
                    "ports": [self._port(device.id, p.id) for p in device.ports],
                }
            )
        return rows

    def _port(self, device_id: str, port_id: str) -> dict[str, Any]:
        topo = self.topology
        port = topo.ports[port_id]
        link = topo.link_of(port_id)
        state = self.stp.ports.get(port_id)
        peer = topo.peer_port(port_id)
        speed = topo.negotiated_speed(link) if link else 0
        load = 0.0
        if link and link.id in self.traffic.links:
            load = self.traffic.links[link.id].load_mbps
        load += self.traffic.port_load.get(port_id, 0.0)
        return {
            "id": port_id,
            "device_id": device_id,
            "index": port.index,
            "label": port.label,
            "media": port.spec.media,
            "role": port.spec.role,
            "max_speed_mbps": port.max_speed_mbps,
            "speed_mbps": speed,
            "enabled": port.enabled,
            "poe_out": port.spec.poe_out,
            "poe_max_w": port.spec.poe_max_w,
            "poe_enabled": port.poe_enabled,
            "poe_delivered_w": round(
                self.power.delivered_w.get(peer.device_id, 0.0), 1
            )
            if peer and port.spec.poe_out and port.poe_enabled
            else 0.0,
            "bpdu_guard": port.bpdu_guard,
            "link_id": link.id if link else None,
            "peer_port_id": peer.id if peer else None,
            "peer_device_id": peer.device_id if peer else None,
            "stp_role": state.role if state else None,
            "stp_state": state.state if state else "forwarding",
            "stp_cost": state.cost if state else 0,
            "stp_reason": state.reason if state else "",
            "edge": state.edge if state else False,
            "load_mbps": round(load, 2),
            "utilisation": round(min(load / speed, 1.0), 4) if speed else 0.0,
            "client_ids": [c.id for c in topo.clients_of_port(port_id)],
        }

    def _links(self) -> list[dict[str, Any]]:
        topo = self.topology
        rows = []
        for link in self.site.links:
            a, b = topo.ports[link.a], topo.ports[link.b]
            a_dev, b_dev = topo.devices[a.device_id], topo.devices[b.device_id]
            load = self.traffic.links.get(link.id)
            rows.append(
                {
                    "id": link.id,
                    "cable": link.cable,
                    "enabled": link.enabled,
                    "state": self.stp.link_state(link.id),
                    "speed_mbps": topo.negotiated_speed(link),
                    "a_port_id": a.id,
                    "b_port_id": b.id,
                    "a_device_id": a_dev.id,
                    "b_device_id": b_dev.id,
                    "a_label": f"{a_dev.name} · {a.label}",
                    "b_label": f"{b_dev.name} · {b.label}",
                    "a_stp_role": self.stp.ports[a.id].role if a.id in self.stp.ports else None,
                    "b_stp_role": self.stp.ports[b.id].role if b.id in self.stp.ports else None,
                    "load_mbps": round(load.load_mbps, 2) if load else 0.0,
                    "utilisation": round(load.utilisation, 4) if load else 0.0,
                    "storm": load.storm if load else False,
                }
            )
        return rows

    def _clients(self) -> list[dict[str, Any]]:
        topo = self.topology
        by_id = {f.id: f for f in self.traffic.flows}
        rows = []
        for client in self.site.clients:
            down = by_id.get(f"client:{client.id}:down")
            up = by_id.get(f"client:{client.id}:up")
            anchor = client.ap_id
            port_label = None
            if client.port_id and client.port_id in topo.ports:
                port = topo.ports[client.port_id]
                anchor = port.device_id
                port_label = port.label
            rows.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "kind": client.kind,
                    "mac": client.mac,
                    "ip": client.ip,
                    "category": client.category,
                    "device_id": anchor,
                    "device_name": topo.devices[anchor].name
                    if anchor in topo.devices
                    else None,
                    "port_id": client.port_id,
                    "port_label": port_label,
                    "rssi_dbm": client.rssi_dbm if client.kind == "wireless" else None,
                    "down_mbps": round(down.delivered_mbps, 2) if down else 0.0,
                    "up_mbps": round(up.delivered_mbps, 2) if up else 0.0,
                    "status": "online"
                    if (down and down.status != "dropped") or (up and up.status != "dropped")
                    else "offline",
                }
            )
        return rows

    # ---------------------------------------------------------------- helpers
    def _uplink_of(self, device_id: str) -> tuple[str | None, str | None]:
        """Which port faces the root bridge — that is the device's uplink."""
        device = self.topology.devices[device_id]
        if device.spec.routing:
            # A gateway's uplink is the circuit, not another box on the LAN.
            wan = next((p for p in device.ports if p.is_wan and p.enabled), None)
            if wan is not None:
                return None, wan.id
        bridge = self.stp.bridges.get(device_id)
        if bridge and bridge.root_port_id:
            peer = self.topology.peer_port(bridge.root_port_id)
            if peer:
                return peer.device_id, bridge.root_port_id
        for port in self.topology.devices[device_id].ports:
            if port.is_wan:
                continue
            link = self.topology.link_of(port.id)
            if link and link.id in self.stp.active_link_ids:
                peer = self.topology.peer_port(port.id)
                if peer and self.topology.devices[peer.device_id].spec.switching:
                    return peer.device_id, port.id
        return None, None

    def _device_status(self, device_id: str, offline: bool) -> str:
        if offline:
            return "offline"
        for issue in self.issues:
            if issue.severity is not Severity.CRITICAL:
                continue
            if any(s.kind == "device" and s.id == device_id for s in issue.subjects):
                return "error"
        return "online"


def simulate(site: SimSite, t: float = 0.0) -> SimulationResult:
    """Run every analysis pass over a site and collect the results.

    The site is copied first, so callers can hand in their live objects without
    the simulator mutating them when it takes unpowered devices offline.
    """
    site = copy.deepcopy(site)
    topo = Topology(site)

    power = power_mod.compute(topo)
    for device_id in power.offline_device_ids:
        topo.devices[device_id].enabled = False

    stp = stp_mod.compute(topo)
    traffic = traffic_mod.compute(topo, stp, t=t)

    issues = sort_issues(
        power.issues + stp.issues + traffic.issues + _config_issues(topo)
    )
    return SimulationResult(
        site=site,
        topology=topo,
        stp=stp,
        power=power,
        traffic=traffic,
        issues=issues,
        t=t,
    )


def _config_issues(topo: Topology) -> list[Issue]:
    """Cabling and configuration mistakes that are not STP or power problems."""
    issues: list[Issue] = []
    for link in topo.site.links:
        a, b = topo.ports.get(link.a), topo.ports.get(link.b)
        if a is None or b is None:
            continue
        a_dev, b_dev = topo.devices[a.device_id], topo.devices[b.device_id]
        label = f"{a_dev.name} {a.label} → {b_dev.name} {b.label}"
        subjects = (Subject("link", link.id, label),)

        if a.is_wan != b.is_wan:
            wan_port, lan_port = (a, b) if a.is_wan else (b, a)
            wan_dev = topo.devices[wan_port.device_id]
            issues.append(
                Issue(
                    code="topology.wan_into_lan",
                    severity=Severity.WARNING,
                    category="config",
                    title=f"{wan_dev.name} WAN is patched into the LAN",
                    detail=(
                        f"{wan_dev.name} {wan_port.label} is a WAN port but it is cabled "
                        f"to {topo.devices[lan_port.device_id].name} {lan_port.label}. "
                        "That double-NATs everything behind this gateway."
                    ),
                    recommendation=(
                        "Patch the WAN port to your upstream circuit, not back into the LAN."
                    ),
                    subjects=subjects,
                )
            )

        negotiated = topo.negotiated_speed(link)
        slowest_port = min(a.max_speed_mbps, b.max_speed_mbps)
        if negotiated < slowest_port:
            issues.append(
                Issue(
                    code="link.cable_limited",
                    severity=Severity.WARNING,
                    category="config",
                    title=f"{link.cable} cable is holding {label} to {negotiated} Mbps",
                    detail=(
                        f"Both ports can run at {slowest_port} Mbps but the cable grade "
                        f"caps the link at {negotiated} Mbps."
                    ),
                    recommendation="Re-terminate with Cat6a, DAC or fibre.",
                    subjects=subjects,
                )
            )
        elif a.max_speed_mbps != b.max_speed_mbps:
            issues.append(
                Issue(
                    code="link.speed_mismatch",
                    severity=Severity.INFO,
                    category="config",
                    title=f"{label} negotiated down to {negotiated} Mbps",
                    detail=(
                        f"{a_dev.name} {a.label} is a {a.max_speed_mbps} Mbps port and "
                        f"{b_dev.name} {b.label} is {b.max_speed_mbps} Mbps."
                    ),
                    recommendation="Match the port speeds to use the full capacity.",
                    subjects=subjects,
                )
            )

    for client in topo.site.clients:
        if client.kind == "wired" and not client.port_id:
            issues.append(
                Issue(
                    code="client.unattached",
                    severity=Severity.INFO,
                    category="config",
                    title=f"{client.name} is not plugged in",
                    detail="This wired client has no switch port assigned.",
                    recommendation="Assign it to a port on a switch.",
                    subjects=(Subject("client", client.id, client.name),),
                )
            )
        if client.kind == "wireless" and not client.ap_id:
            issues.append(
                Issue(
                    code="client.no_ap",
                    severity=Severity.INFO,
                    category="config",
                    title=f"{client.name} has no access point",
                    detail="This wireless client is not associated with an AP.",
                    recommendation="Associate it with an access point.",
                    subjects=(Subject("client", client.id, client.name),),
                )
            )
    return issues
