"""The UniFi hardware catalogue.

Device definitions live in ``data/catalog.json`` so that adding a model is a
data change, not a code change. Port groups in the JSON are expanded here into
flat, individually addressable ports.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

_DATA = Path(__file__).parent / "data" / "catalog.json"

#: Physical media families. Ports can only be cabled together within a family.
MEDIA_FAMILY = {
    "rj45": "copper",
    "sfp": "fibre",
    "sfp+": "fibre",
    "sfp28": "fibre",
}

#: Watts each PoE standard can deliver at the port (PSE side).
POE_STANDARD_WATTS = {
    "802.3af": 15.4,
    "802.3at": 30.0,
    "802.3bt": 60.0,
    "802.3bt-type4": 90.0,
    "passive-24v": 17.0,
}

#: Ranking used when checking whether a switch port can power a device.
POE_STANDARD_RANK = {
    "passive-24v": 0,
    "802.3af": 1,
    "802.3at": 2,
    "802.3bt": 3,
    "802.3bt-type4": 4,
}


@dataclass(frozen=True)
class PortSpec:
    """A single physical port as the hardware ships it."""

    index: int
    label: str
    media: str
    speed_mbps: int
    role: str  # lan | wan | uplink
    poe_out: str | None = None
    poe_max_w: float = 0.0
    poe_in: str | None = None

    @property
    def media_family(self) -> str:
        return MEDIA_FAMILY.get(self.media, self.media)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "label": self.label,
            "media": self.media,
            "media_family": self.media_family,
            "speed_mbps": self.speed_mbps,
            "role": self.role,
            "poe_out": self.poe_out,
            "poe_max_w": self.poe_max_w,
            "poe_in": self.poe_in,
        }


@dataclass(frozen=True)
class DeviceSpec:
    """A catalogue entry: what the hardware is and what it can do."""

    key: str
    name: str
    short: str
    line: str  # gateway | switch | ap | protect | other
    family: str
    description: str
    ports: tuple[PortSpec, ...]
    routing: bool = False
    switching: bool = False
    wireless: bool = False
    stp_capable: bool = False
    powered_by: str = "ac"
    poe_in: str | None = None
    power_draw_w: float = 0.0
    poe_budget_w: float = 0.0
    switching_capacity_mbps: int = 0
    wan_capacity_mbps: int = 0
    wireless_capacity_mbps: int = 0
    max_wireless_clients: int = 0

    @cached_property
    def ports_by_index(self) -> dict[int, PortSpec]:
        return {p.index: p for p in self.ports}

    @property
    def port_count(self) -> int:
        return len(self.ports)

    @property
    def needs_poe(self) -> bool:
        """True when the device has no wall power and must be fed by a PSE."""
        return self.powered_by == "poe" and self.poe_in is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "short": self.short,
            "line": self.line,
            "family": self.family,
            "description": self.description,
            "routing": self.routing,
            "switching": self.switching,
            "wireless": self.wireless,
            "stp_capable": self.stp_capable,
            "powered_by": self.powered_by,
            "poe_in": self.poe_in,
            "power_draw_w": self.power_draw_w,
            "poe_budget_w": self.poe_budget_w,
            "switching_capacity_mbps": self.switching_capacity_mbps,
            "wan_capacity_mbps": self.wan_capacity_mbps,
            "wireless_capacity_mbps": self.wireless_capacity_mbps,
            "max_wireless_clients": self.max_wireless_clients,
            "port_count": self.port_count,
            "ports": [p.to_dict() for p in self.ports],
        }


class Catalog:
    """Lazily-loaded, read-only view over the catalogue file."""

    def __init__(self, path: Path = _DATA) -> None:
        self._path = path
        self._specs: dict[str, DeviceSpec] | None = None
        self._version = ""

    def _load(self) -> dict[str, DeviceSpec]:
        if self._specs is None:
            raw = json.loads(self._path.read_text())
            self._version = raw.get("version", "unknown")
            self._specs = {
                entry["key"]: _build_spec(entry) for entry in raw["models"]
            }
        return self._specs

    @property
    def version(self) -> str:
        self._load()
        return self._version

    def __getitem__(self, key: str) -> DeviceSpec:
        try:
            return self._load()[key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"unknown UniFi model {key!r}") from exc

    def __contains__(self, key: object) -> bool:
        return key in self._load()

    def __iter__(self) -> Iterator[DeviceSpec]:
        return iter(self._load().values())

    def __len__(self) -> int:
        return len(self._load())

    def get(self, key: str, default: DeviceSpec | None = None) -> DeviceSpec | None:
        return self._load().get(key, default)

    def keys(self) -> list[str]:
        return list(self._load())

    def by_line(self, line: str) -> list[DeviceSpec]:
        return [s for s in self if s.line == line]


def _build_spec(entry: dict[str, Any]) -> DeviceSpec:
    ports: list[PortSpec] = []
    index = 1
    for group in entry.get("ports", []):
        start = int(group.get("start", 1))
        template = group.get("label", "Port {n}")
        for offset in range(int(group["count"])):
            ports.append(
                PortSpec(
                    index=index,
                    label=template.replace("{n}", str(start + offset)),
                    media=group["media"],
                    speed_mbps=int(group["speed_mbps"]),
                    role=group.get("role", "lan"),
                    poe_out=group.get("poe_out"),
                    poe_max_w=float(group.get("poe_max_w", 0.0)),
                    poe_in=group.get("poe_in"),
                )
            )
            index += 1
    known = {
        "routing", "switching", "wireless", "stp_capable", "powered_by", "poe_in",
        "power_draw_w", "poe_budget_w", "switching_capacity_mbps", "wan_capacity_mbps",
        "wireless_capacity_mbps", "max_wireless_clients",
    }
    extras = {k: entry[k] for k in known if k in entry}
    return DeviceSpec(
        key=entry["key"],
        name=entry["name"],
        short=entry["short"],
        line=entry["line"],
        family=entry["family"],
        description=entry.get("description", ""),
        ports=tuple(ports),
        **extras,
    )


def media_compatible(a: str, b: str) -> bool:
    """Copper to copper, fibre to fibre. SFP and SFP+ cages interoperate."""
    return MEDIA_FAMILY.get(a, a) == MEDIA_FAMILY.get(b, b)


def poe_meets(supplied: str | None, required: str | None) -> bool:
    """Does a PSE standard satisfy what a powered device asks for?"""
    if required is None:
        return True
    if supplied is None:
        return False
    return POE_STANDARD_RANK.get(supplied, -1) >= POE_STANDARD_RANK.get(required, 99)


CATALOG = Catalog()
