"""The site graph: devices, ports, cables, clients and flows.

Everything the engine needs is expressed with plain dataclasses so the core can
be driven from Django, from a YAML blueprint, or straight from a unit test.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from simcore.catalog import CATALOG, DeviceSpec, PortSpec, media_compatible

#: Maximum negotiated rate a cable grade can carry, in Mbps.
CABLE_MAX_MBPS = {
    "cat5e": 2500,
    "cat6": 10000,
    "cat6a": 25000,
    "dac": 25000,
    "fibre": 25000,
}

#: Which cable grades belong to which media family.
CABLE_MEDIA = {
    "cat5e": "copper",
    "cat6": "copper",
    "cat6a": "copper",
    "dac": "fibre",
    "fibre": "fibre",
}

PortState = Literal["forwarding", "discarding", "disabled", "err-disabled"]


@dataclass
class SimPort:
    id: str
    device_id: str
    spec: PortSpec
    name: str = ""
    enabled: bool = True
    poe_enabled: bool = True
    edge: bool = False
    bpdu_guard: bool = False
    speed_override: int | None = None

    @property
    def index(self) -> int:
        return self.spec.index

    @property
    def label(self) -> str:
        return self.name or self.spec.label

    @property
    def max_speed_mbps(self) -> int:
        if self.speed_override:
            return min(self.speed_override, self.spec.speed_mbps)
        return self.spec.speed_mbps

    @property
    def is_wan(self) -> bool:
        return self.spec.role == "wan"


@dataclass
class SimDevice:
    id: str
    model: str
    name: str
    mac: str = ""
    ip: str = ""
    ports: list[SimPort] = field(default_factory=list)
    enabled: bool = True
    stp_enabled: bool = True
    stp_priority: int = 32768
    x: float = 0.0
    y: float = 0.0

    @property
    def spec(self) -> DeviceSpec:
        return CATALOG[self.model]

    @property
    def line(self) -> str:
        return self.spec.line

    @property
    def bridge_id(self) -> tuple[int, str]:
        """802.1D bridge identifier: priority first, MAC as tie-break."""
        return (self.stp_priority, self.mac.lower())

    @property
    def forwards_frames(self) -> bool:
        """Does this box pass ethernet frames between its ports at all?"""
        return self.spec.switching or self.spec.wireless

    def port(self, index: int) -> SimPort | None:
        for p in self.ports:
            if p.index == index:
                return p
        return None

    @classmethod
    def from_model(cls, device_id: str, model: str, name: str, **kwargs: Any) -> SimDevice:
        """Build a device with the full port complement of its catalogue entry."""
        spec = CATALOG[model]
        dev = cls(id=device_id, model=model, name=name, **kwargs)
        dev.ports = [
            SimPort(id=f"{device_id}:{p.index}", device_id=device_id, spec=p)
            for p in spec.ports
        ]
        return dev


@dataclass
class SimLink:
    id: str
    a: str  # port id
    b: str  # port id
    cable: str = "cat6"
    enabled: bool = True

    def other(self, port_id: str) -> str:
        return self.b if port_id == self.a else self.a


@dataclass
class SimClient:
    id: str
    name: str
    kind: Literal["wired", "wireless"] = "wired"
    mac: str = ""
    ip: str = ""
    port_id: str | None = None  # wired attachment
    ap_id: str | None = None  # wireless attachment
    category: str = "workstation"
    down_mbps: float = 5.0
    up_mbps: float = 1.0
    rssi_dbm: int = -55


@dataclass
class SimFlow:
    """A synthetic traffic generator between two endpoints."""

    id: str
    name: str
    src_kind: Literal["client", "device", "internet"]
    src_id: str
    dst_kind: Literal["client", "device", "internet"]
    dst_id: str
    mbps: float = 100.0
    protocol: str = "tcp"
    enabled: bool = True
    burstiness: float = 0.15


@dataclass
class SimSite:
    id: str
    name: str
    stp_mode: Literal["rstp", "stp", "disabled"] = "rstp"
    wan_download_mbps: float = 1000.0
    wan_upload_mbps: float = 1000.0
    devices: list[SimDevice] = field(default_factory=list)
    links: list[SimLink] = field(default_factory=list)
    clients: list[SimClient] = field(default_factory=list)
    flows: list[SimFlow] = field(default_factory=list)


class LinkError(ValueError):
    """Raised when two ports cannot legally be cabled together."""


class Topology:
    """Indexed, query-friendly view over a :class:`SimSite`."""

    def __init__(self, site: SimSite) -> None:
        self.site = site
        self.devices: dict[str, SimDevice] = {d.id: d for d in site.devices}
        self.ports: dict[str, SimPort] = {
            p.id: p for d in site.devices for p in d.ports
        }
        self.clients: dict[str, SimClient] = {c.id: c for c in site.clients}
        self.links: dict[str, SimLink] = {link.id: link for link in site.links}
        self._port_link: dict[str, SimLink] = {}
        for link in site.links:
            self._port_link[link.a] = link
            self._port_link[link.b] = link

    # ------------------------------------------------------------------ lookups
    def device_of(self, port_id: str) -> SimDevice:
        return self.devices[self.ports[port_id].device_id]

    def link_of(self, port_id: str) -> SimLink | None:
        return self._port_link.get(port_id)

    def peer_port(self, port_id: str) -> SimPort | None:
        link = self._port_link.get(port_id)
        if link is None:
            return None
        return self.ports.get(link.other(port_id))

    def links_of(self, device_id: str) -> list[SimLink]:
        return [
            link
            for link in self.site.links
            if self.ports[link.a].device_id == device_id
            or self.ports[link.b].device_id == device_id
        ]

    def clients_of_port(self, port_id: str) -> list[SimClient]:
        return [c for c in self.site.clients if c.port_id == port_id]

    def clients_of_ap(self, ap_id: str) -> list[SimClient]:
        return [c for c in self.site.clients if c.ap_id == ap_id]

    # -------------------------------------------------------------- link health
    def negotiated_speed(self, link: SimLink) -> int:
        a, b = self.ports[link.a], self.ports[link.b]
        cable_cap = CABLE_MAX_MBPS.get(link.cable, 25000)
        return min(a.max_speed_mbps, b.max_speed_mbps, cable_cap)

    def link_up(self, link: SimLink) -> bool:
        """A cable only carries traffic when both ends are alive."""
        if not link.enabled:
            return False
        a, b = self.ports.get(link.a), self.ports.get(link.b)
        if a is None or b is None or not a.enabled or not b.enabled:
            return False
        return self.devices[a.device_id].enabled and self.devices[b.device_id].enabled

    def is_bridge(self, device: SimDevice) -> bool:
        """Does this device take part in spanning tree?"""
        return (
            device.enabled
            and device.spec.stp_capable
            and device.stp_enabled
            and self.site.stp_mode != "disabled"
        )

    def l2_ports(self, device: SimDevice) -> list[SimPort]:
        """Ports inside the layer 2 domain. A router does not bridge its WAN."""
        return [p for p in device.ports if not p.is_wan]

    def is_l2_link(self, link: SimLink) -> bool:
        a, b = self.ports.get(link.a), self.ports.get(link.b)
        if a is None or b is None:
            return False
        return not a.is_wan and not b.is_wan

    def uplink_candidates(self) -> list[SimDevice]:
        return [d for d in self.site.devices if d.spec.routing and d.enabled]

    # ------------------------------------------------------------- link editing
    def validate_link(
        self, port_a_id: str, port_b_id: str, cable: str = "cat6"
    ) -> None:
        """Raise :class:`LinkError` if this cable could not physically exist."""
        if port_a_id == port_b_id:
            raise LinkError("A port cannot be patched into itself.")
        for pid in (port_a_id, port_b_id):
            if pid not in self.ports:
                raise LinkError(f"Unknown port {pid!r}.")
            if pid in self._port_link:
                port = self.ports[pid]
                dev = self.devices[port.device_id]
                raise LinkError(f"{dev.name} {port.label} is already patched.")
        a, b = self.ports[port_a_id], self.ports[port_b_id]
        if not media_compatible(a.spec.media, b.spec.media):
            raise LinkError(
                f"{a.spec.media.upper()} cannot be patched to {b.spec.media.upper()}."
            )
        if cable not in CABLE_MEDIA:
            raise LinkError(f"Unknown cable type {cable!r}.")
        if CABLE_MEDIA[cable] != a.spec.media_family:
            raise LinkError(
                f"{cable} is a {CABLE_MEDIA[cable]} cable; "
                f"{a.label} is {a.spec.media_family}."
            )

    def available_ports(self, device_id: str | None = None) -> list[SimPort]:
        ports: Iterable[SimPort] = self.ports.values()
        if device_id:
            ports = [p for p in ports if p.device_id == device_id]
        return [p for p in ports if p.id not in self._port_link]
