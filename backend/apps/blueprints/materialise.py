"""Blueprint materialisation — pure function, no ORM, no I/O.

Converts a validated blueprint ``parsed_data`` dict into a list of
``DeviceSpec`` objects that the fleet service can use to create VirtualDevice
rows and that the engine can turn into running virtual devices.

Deterministic MACs follow the ``02:00:00:XX:XX:XX`` LAA scheme keyed on
(blueprint_slug, hostname) so re-instantiation of the same blueprint
always produces the same MAC — the controller won't see a "new" device.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceSpec:
    """Specification for one virtual device derived from a blueprint entry."""

    hostname: str
    model_code: str
    mac_address: str
    blueprint_slug: str
    position: int
    network: str | None = None
    uplink: str | None = None
    tags: list[str] = field(default_factory=list)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _deterministic_mac(blueprint_slug: str, hostname: str) -> str:
    h = hashlib.sha256(f"{blueprint_slug}|{hostname}".encode()).digest()
    b = [0x02, 0x00, 0x00, h[0], h[1], h[2]]
    return ":".join(f"{x:02x}" for x in b)


def materialise(
    parsed_data: dict[str, Any],
    *,
    blueprint_slug: str = "",
    fallback_model: str = "unknown",
) -> list[DeviceSpec]:
    """Convert blueprint ``parsed_data`` → ordered list of ``DeviceSpec``.

    Parameters
    ----------
    parsed_data:
        The already-validated parsed blueprint dict (from ``validator.parse_yaml``).
    blueprint_slug:
        Stable slug used as part of the MAC seed. Callers derive this from
        the blueprint's ``name`` field or UUID.
    fallback_model:
        Used when a device entry has no ``model`` key.

    Returns
    -------
    list[DeviceSpec]
        One entry per ``site.devices`` entry, in declaration order.
    """
    if not blueprint_slug:
        blueprint_slug = _slugify(parsed_data.get("name") or "unknown")

    site: dict[str, Any] = parsed_data.get("site", {})
    raw_devices: list[dict[str, Any]] = site.get("devices", []) or []

    specs: list[DeviceSpec] = []
    for idx, dev in enumerate(raw_devices):
        hostname = str(dev.get("hostname") or f"device-{idx}")
        model_code = str(dev.get("model") or fallback_model)
        mac = _deterministic_mac(blueprint_slug, hostname)
        specs.append(
            DeviceSpec(
                hostname=hostname,
                model_code=model_code,
                mac_address=mac,
                blueprint_slug=blueprint_slug,
                position=idx,
                network=dev.get("network") or None,
                uplink=dev.get("uplink") or None,
                tags=list(dev.get("tags") or []),
            )
        )
    return specs
