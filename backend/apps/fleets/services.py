"""Domain services for fleets.

Splits fleet lifecycle across the process boundary per
``Components/23 - Fleet Manager``:

- Django (this module) — validation, creating Fleet + VirtualDevice rows,
  publishing work to the worker via ``worker_commands``.
- Worker (``engine.supervisor``) — spawning tasks, ramping, auto-adopt,
  teardown. Phase 1 shipped the basic spawn path; ramping and auto-adopt
  are Phase 2+.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.common.worker_commands import CHANNEL_DEVICES, publish_worker_command
from apps.devices.services import create_device, deterministic_mac

from .models import Fleet

_MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def instantiate_fleet(fleet: Fleet) -> list[str]:
    """Materialise ``fleet`` into virtual devices.

    Two modes:

    - If ``fleet.blueprint`` is set, iterate ``parsed_json.site.devices``
      and create one row per entry, honouring hostname/model/mac overrides.
      ``device_count`` is set to the resulting count.
    - Otherwise (simple mode), create ``fleet.device_count`` rows, all of
      ``fleet.model_code``.

    Runs inside a transaction; spawn commands fire only after commit.
    """
    device_ids: list[str] = []
    with transaction.atomic():
        fleet.state = Fleet.STATE_RAMPING
        fleet.save(update_fields=["state"])

        if fleet.blueprint_id is not None:
            device_ids = _instantiate_from_blueprint(fleet)
            fleet.device_count = len(device_ids)
            fleet.save(update_fields=["device_count"])
        else:
            device_ids = _instantiate_simple(fleet)

    for device_id in device_ids:
        publish_worker_command(CHANNEL_DEVICES, action="spawn", device_id=device_id)
    return device_ids


def _instantiate_simple(fleet: Fleet) -> list[str]:
    device_ids: list[str] = []
    for _ in range(fleet.device_count):
        device = create_device(
            model_code=fleet.model_code,
            controller_target_id=str(fleet.controller_target_id),
            fleet_id=str(fleet.id),
        )
        device_ids.append(str(device.id))
    return device_ids


def _instantiate_from_blueprint(fleet: Fleet) -> list[str]:
    parsed: dict[str, Any] = fleet.blueprint.parsed_json or {}
    site: dict[str, Any] = parsed.get("site", {})
    devices: list[dict[str, Any]] = site.get("devices", []) or []
    slug = _slugify(parsed.get("name") or str(fleet.blueprint_id))

    device_ids: list[str] = []
    for dev in devices:
        hostname = str(dev.get("hostname") or "")
        model = str(dev.get("model") or fleet.model_code or "unknown")
        mac = dev.get("mac")
        if not (isinstance(mac, str) and _MAC_RE.match(mac)):
            mac = deterministic_mac(blueprint_slug=slug, hostname=hostname)
        device = create_device(
            model_code=model,
            controller_target_id=str(fleet.controller_target_id),
            fleet_id=str(fleet.id),
            hostname=hostname,
            mac_address=mac,
        )
        device_ids.append(str(device.id))
    return device_ids


def pause(fleet: Fleet) -> Fleet:
    fleet.state = Fleet.STATE_PAUSED
    fleet.save(update_fields=["state"])
    for device in fleet.devices.all():
        publish_worker_command(CHANNEL_DEVICES, action="despawn", device_id=str(device.id))
    return fleet


def resume(fleet: Fleet) -> Fleet:
    fleet.state = Fleet.STATE_ACTIVE
    fleet.save(update_fields=["state"])
    for device in fleet.devices.all():
        publish_worker_command(CHANNEL_DEVICES, action="spawn", device_id=str(device.id))
    return fleet


def teardown(fleet: Fleet) -> Fleet:
    """Mark the fleet retired, despawn all devices, keep rows for audit."""
    fleet.state = Fleet.STATE_TEARING_DOWN
    fleet.retired_at = timezone.now()
    fleet.save(update_fields=["state", "retired_at"])
    for device in fleet.devices.all():
        publish_worker_command(CHANNEL_DEVICES, action="despawn", device_id=str(device.id))
    fleet.state = Fleet.STATE_DELETED
    fleet.save(update_fields=["state"])
    return fleet
