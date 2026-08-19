"""Domain logic for building and simulating a virtual site.

Views stay thin: they validate input, call in here, and serialise the result.
"""

from __future__ import annotations

import time
from typing import Any, Literal, cast

from django.db import transaction

from netsim.models import Client, Device, Flow, Link, Network, Port, Site
from simcore.builder import generate_mac
from simcore.catalog import CATALOG
from simcore.engine import SimulationResult, simulate
from simcore.topology import (
    LinkError,
    SimClient,
    SimDevice,
    SimFlow,
    SimLink,
    SimPort,
    SimSite,
    Topology,
)


# --------------------------------------------------------------------- mapping
def build_sim_site(site: Site) -> SimSite:
    """Project the database rows onto the framework-free simulation model."""
    sim = SimSite(
        id=str(site.pk),
        name=site.name,
        stp_mode=cast(Literal["rstp", "stp", "disabled"], site.stp_mode),
        wan_download_mbps=float(site.wan_download_mbps),
        wan_upload_mbps=float(site.wan_upload_mbps),
    )
    devices = site.devices.prefetch_related("ports").all()
    for device in devices:
        spec = CATALOG[device.model]
        sim_device = SimDevice(
            id=str(device.pk),
            model=device.model,
            name=device.name,
            mac=device.mac or generate_mac(str(device.pk)),
            ip=device.ip or "",
            enabled=device.enabled,
            stp_enabled=device.stp_enabled,
            stp_priority=device.stp_priority,
            x=device.x,
            y=device.y,
        )
        by_index = {p.index: p for p in device.ports.all()}
        for port_spec in spec.ports:
            row = by_index.get(port_spec.index)
            sim_device.ports.append(
                SimPort(
                    id=f"{device.pk}:{port_spec.index}",
                    device_id=str(device.pk),
                    spec=port_spec,
                    name=row.name if row else "",
                    enabled=row.enabled if row else True,
                    poe_enabled=row.poe_enabled if row else True,
                    bpdu_guard=row.bpdu_guard if row else False,
                    speed_override=row.speed_override if row else None,
                )
            )
        sim.devices.append(sim_device)

    for link in site.links.select_related("a_port", "b_port").all():
        sim.links.append(
            SimLink(
                id=str(link.pk),
                a=link.a_port.sim_id,
                b=link.b_port.sim_id,
                cable=link.cable,
                enabled=link.enabled,
            )
        )

    for client in site.clients.select_related("port").all():
        sim.clients.append(
            SimClient(
                id=str(client.pk),
                name=client.name,
                kind=cast(Literal["wired", "wireless"], client.kind),
                mac=client.mac or generate_mac(f"client-{client.pk}"),
                ip=client.ip or "",
                port_id=client.port.sim_id if client.port else None,
                ap_id=str(client.access_point_id) if client.access_point_id else None,
                category=client.category,
                down_mbps=client.down_mbps,
                up_mbps=client.up_mbps,
                rssi_dbm=client.rssi_dbm,
            )
        )

    for flow in site.flows.all():
        src_kind, src_id = flow.endpoint("src")
        dst_kind, dst_id = flow.endpoint("dst")
        sim.flows.append(
            SimFlow(
                id=str(flow.pk),
                name=flow.name,
                src_kind=cast(Literal["client", "device", "internet"], src_kind),
                src_id=src_id,
                dst_kind=cast(Literal["client", "device", "internet"], dst_kind),
                dst_id=dst_id,
                mbps=flow.mbps,
                protocol=flow.protocol,
                enabled=flow.enabled,
                burstiness=flow.burstiness,
            )
        )
    return sim


def run_simulation(site: Site, t: float | None = None) -> SimulationResult:
    """Simulate the site at wall-clock time ``t`` (seconds)."""
    return simulate(build_sim_site(site), t=time.time() if t is None else t)


def topology_for(site: Site) -> Topology:
    return Topology(build_sim_site(site))


# ------------------------------------------------------------------- mutations
@transaction.atomic
def create_device(
    site: Site,
    model: str,
    name: str | None = None,
    x: float = 0,
    y: float = 0,
    **extra: Any,
) -> Device:
    """Add a catalogue device and materialise every one of its ports."""
    if model not in CATALOG:
        raise ValueError(f"{model!r} is not in the UniFi catalogue.")
    spec = CATALOG[model]
    if not x and not y:
        x, y = _free_position(site)
    device = Device.objects.create(
        site=site,
        model=model,
        name=name or _unique_name(site, spec.short),
        x=x,
        y=y,
        **extra,
    )
    device.mac = device.mac or generate_mac(str(device.pk))
    device.ip = device.ip or _next_ip(site)
    device.save(update_fields=["mac", "ip"])
    Port.objects.bulk_create(
        [Port(device=device, index=port.index) for port in spec.ports]
    )
    return device


#: Spacing used when auto-placing a device on the topology canvas.
GRID_X, GRID_Y, GRID_COLUMNS = 300, 240, 4


def _free_position(site: Site) -> tuple[float, float]:
    """Drop a new device into the first empty slot on a loose grid."""
    taken = {(round(d.x), round(d.y)) for d in site.devices.all()}
    for slot in range(GRID_COLUMNS * 40):
        x = (slot % GRID_COLUMNS) * GRID_X - (GRID_COLUMNS - 1) * GRID_X / 2
        y = (slot // GRID_COLUMNS) * GRID_Y
        if not any(
            abs(x - used_x) < GRID_X / 2 and abs(y - used_y) < GRID_Y / 2
            for used_x, used_y in taken
        ):
            return x, y
    return 0.0, float(len(taken) * GRID_Y)


def _unique_name(site: Site, base: str) -> str:
    existing = set(site.devices.values_list("name", flat=True))
    if base not in existing:
        return base
    for suffix in range(2, 200):
        candidate = f"{base} {suffix}"
        if candidate not in existing:
            return candidate
    return f"{base} {len(existing) + 1}"


def _next_ip(site: Site) -> str:
    used = {d.ip for d in site.devices.all() if d.ip}
    for host in range(1, 250):
        candidate = f"10.0.0.{host}"
        if candidate not in used:
            return candidate
    return "10.0.0.254"


@transaction.atomic
def create_link(site: Site, a_port: Port, b_port: Port, cable: str = "cat6") -> Link:
    """Patch two ports together, refusing anything physically impossible."""
    if a_port.device.site_id != site.pk or b_port.device.site_id != site.pk:
        raise LinkError("Both ports must belong to this site.")
    topo = topology_for(site)
    topo.validate_link(a_port.sim_id, b_port.sim_id, cable)
    return Link.objects.create(site=site, a_port=a_port, b_port=b_port, cable=cable)


def available_ports(site: Site, device: Device | None = None) -> list[Port]:
    """Ports with nothing patched into them, newest catalogue order preserved."""
    patched = set(Link.objects.filter(site=site).values_list("a_port_id", flat=True)) | set(
        Link.objects.filter(site=site).values_list("b_port_id", flat=True)
    )
    query = Port.objects.filter(device__site=site).select_related("device")
    if device is not None:
        query = query.filter(device=device)
    return [p for p in query if p.pk not in patched]


# ---------------------------------------------------------------- blueprints
def export_blueprint(site: Site) -> dict[str, Any]:
    """Serialise a whole site into a portable, human-editable structure."""
    return {
        "version": 1,
        "site": {
            "name": site.name,
            "description": site.description,
            "stp_mode": site.stp_mode,
            "wan_download_mbps": site.wan_download_mbps,
            "wan_upload_mbps": site.wan_upload_mbps,
        },
        "networks": [
            {
                "name": n.name,
                "vlan_id": n.vlan_id,
                "subnet": n.subnet,
                "purpose": n.purpose,
                "isolated": n.isolated,
            }
            for n in site.networks.all()
        ],
        "devices": [
            {
                "key": str(d.pk),
                "name": d.name,
                "model": d.model,
                "ip": d.ip,
                "x": d.x,
                "y": d.y,
                "stp_enabled": d.stp_enabled,
                "stp_priority": d.stp_priority,
                "ports": [
                    {
                        "index": p.index,
                        "name": p.name,
                        "enabled": p.enabled,
                        "poe_enabled": p.poe_enabled,
                        "bpdu_guard": p.bpdu_guard,
                    }
                    for p in d.ports.all()
                    if p.name or not p.enabled or not p.poe_enabled or p.bpdu_guard
                ],
            }
            for d in site.devices.prefetch_related("ports")
        ],
        "links": [
            {
                "a": [str(link.a_port.device_id), link.a_port.index],
                "b": [str(link.b_port.device_id), link.b_port.index],
                "cable": link.cable,
                "enabled": link.enabled,
            }
            for link in site.links.select_related("a_port", "b_port")
        ],
        "clients": [
            {
                "name": c.name,
                "kind": c.kind,
                "category": c.category,
                "ip": c.ip,
                "port": [str(c.port.device_id), c.port.index] if c.port else None,
                "access_point": str(c.access_point_id) if c.access_point_id else None,
                "down_mbps": c.down_mbps,
                "up_mbps": c.up_mbps,
                "rssi_dbm": c.rssi_dbm,
            }
            for c in site.clients.select_related("port")
        ],
        "flows": [
            {
                "name": f.name,
                "enabled": f.enabled,
                "protocol": f.protocol,
                "mbps": f.mbps,
                "src": _blueprint_endpoint(f, "src"),
                "dst": _blueprint_endpoint(f, "dst"),
            }
            for f in site.flows.select_related("src_client", "dst_client")
        ],
    }


def _blueprint_endpoint(flow: Flow, side: str) -> list[str]:
    """Reference clients by name and devices by key, so a blueprint is portable.

    Client names therefore have to be unique within a site for a flow to survive
    an export/import round trip.
    """
    kind = getattr(flow, f"{side}_kind")
    if kind == "client":
        client = getattr(flow, f"{side}_client")
        return ["client", client.name] if client else ["internet", "internet"]
    if kind == "device":
        device_id = getattr(flow, f"{side}_device_id")
        return ["device", str(device_id)] if device_id else ["internet", "internet"]
    return ["internet", "internet"]


@transaction.atomic
def import_blueprint(blueprint: dict[str, Any], name: str | None = None) -> Site:
    """Recreate a site from :func:`export_blueprint` output."""
    meta = blueprint.get("site", {})
    site = Site.objects.create(
        name=_unique_site_name(name or meta.get("name", "Imported site")),
        description=meta.get("description", ""),
        stp_mode=meta.get("stp_mode", "rstp"),
        wan_download_mbps=meta.get("wan_download_mbps", 1000),
        wan_upload_mbps=meta.get("wan_upload_mbps", 1000),
    )
    for entry in blueprint.get("networks", []):
        Network.objects.create(site=site, **entry)

    devices: dict[str, Device] = {}
    for entry in blueprint.get("devices", []):
        device = create_device(
            site,
            entry["model"],
            name=entry.get("name"),
            x=entry.get("x", 0),
            y=entry.get("y", 0),
            stp_enabled=entry.get("stp_enabled", True),
            stp_priority=entry.get("stp_priority", 32768),
        )
        if entry.get("ip"):
            device.ip = entry["ip"]
            device.save(update_fields=["ip"])
        devices[str(entry.get("key", entry.get("name")))] = device
        for port_entry in entry.get("ports", []):
            Port.objects.filter(device=device, index=port_entry["index"]).update(
                name=port_entry.get("name", ""),
                enabled=port_entry.get("enabled", True),
                poe_enabled=port_entry.get("poe_enabled", True),
                bpdu_guard=port_entry.get("bpdu_guard", False),
            )

    def resolve(ref: list[Any]) -> Port:
        device = devices[str(ref[0])]
        return Port.objects.get(device=device, index=ref[1])

    for entry in blueprint.get("links", []):
        create_link(site, resolve(entry["a"]), resolve(entry["b"]), entry.get("cable", "cat6"))

    clients: dict[str, Client] = {}
    for entry in blueprint.get("clients", []):
        client = Client.objects.create(
            site=site,
            name=entry["name"],
            kind=entry.get("kind", "wired"),
            category=entry.get("category", "workstation"),
            ip=entry.get("ip") or None,
            port=resolve(entry["port"]) if entry.get("port") else None,
            access_point=devices.get(str(entry.get("access_point"))),
            down_mbps=entry.get("down_mbps", 5),
            up_mbps=entry.get("up_mbps", 1),
            rssi_dbm=entry.get("rssi_dbm", -55),
        )
        client.mac = generate_mac(f"client-{client.pk}")
        client.save(update_fields=["mac"])
        clients[entry["name"]] = client

    for entry in blueprint.get("flows", []):
        src_kind, src_ref = entry.get("src", ["internet", "internet"])
        dst_kind, dst_ref = entry.get("dst", ["internet", "internet"])
        Flow.objects.create(
            site=site,
            name=entry["name"],
            enabled=entry.get("enabled", True),
            protocol=entry.get("protocol", "tcp"),
            mbps=entry.get("mbps", 100),
            src_kind=src_kind,
            src_client=clients.get(src_ref) if src_kind == "client" else None,
            src_device=devices.get(str(src_ref)) if src_kind == "device" else None,
            dst_kind=dst_kind,
            dst_client=clients.get(dst_ref) if dst_kind == "client" else None,
            dst_device=devices.get(str(dst_ref)) if dst_kind == "device" else None,
        )
    return site


def _unique_site_name(name: str) -> str:
    if not Site.objects.filter(name=name).exists():
        return name
    for suffix in range(2, 200):
        candidate = f"{name} ({suffix})"
        if not Site.objects.filter(name=candidate).exists():
            return candidate
    return f"{name} ({Site.objects.count() + 1})"
