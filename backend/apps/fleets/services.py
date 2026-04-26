"""Domain services for fleets.

Splits fleet lifecycle across the process boundary per
``Components/23 - Fleet Manager``:

- Django (this module) — validation, creating Fleet + VirtualDevice rows,
  publishing work to the worker via ``worker_commands``, scheduling the
  state-transition task via Celery countdown, and fanning out fleet
  events onto the Channels layer for live UI updates.
- Worker (``engine.supervisor``) — spawning tasks, honouring per-spawn
  ``delay_ms``, auto-adoption loop, teardown.
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.worker_commands import CHANNEL_DEVICES, publish_worker_command
from apps.devices.services import create_device, deterministic_mac

from .events import publish_fleet_event
from .models import Fleet
from .ramp import compute_delays, ramp_duration_ms
from .tasks import transition_fleet_to_active

_MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _emit_state(fleet: Fleet) -> None:
    publish_fleet_event(
        str(fleet.id),
        "fleet.state_changed",
        state=fleet.state,
        device_count=fleet.device_count,
    )


def instantiate_fleet(fleet: Fleet) -> list[str]:
    """Materialise ``fleet`` into virtual devices and schedule the ramp.

    Order of operations:
    1. Inside a transaction, flip state to 'ramping' and create device rows.
    2. After commit, compute per-device spawn delays from ``ramp_spec`` and
       publish one ``spawn`` command per device with its ``delay_ms``.
    3. Schedule ``transition_fleet_to_active`` to fire after the ramp
       duration (via Celery countdown — inline under eager mode in dev).
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

    _emit_state(fleet)

    delays = compute_delays(len(device_ids), fleet.ramp_spec)
    for device_id, delay_ms in zip(device_ids, delays, strict=False):
        publish_worker_command(
            CHANNEL_DEVICES,
            action="spawn",
            device_id=device_id,
            delay_ms=delay_ms,
            auto_adopt=bool(fleet.auto_adopt),
            fleet_id=str(fleet.id),
        )

    countdown_s = ramp_duration_ms(delays) / 1000.0
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        # Eager mode (dev/tests): countdown semantics vary by Celery
        # version. Run inline — countdown is a production concern.
        transition_fleet_to_active(str(fleet.id))
    else:
        transition_fleet_to_active.apply_async(args=[str(fleet.id)], countdown=countdown_s)

    from apps.system.notifications import push as notify

    notify(
        title=f"Fleet “{fleet.name}” is ramping",
        message=f"{len(device_ids)} devices being provisioned",
        level="info",
        target_type="fleet",
        target_id=str(fleet.id),
    )

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
    _emit_state(fleet)

    from apps.system.notifications import push as notify

    notify(
        title=f"Fleet “{fleet.name}” paused",
        message=f"{fleet.device_count} devices despawned",
        level="warning",
        target_type="fleet",
        target_id=str(fleet.id),
    )

    return fleet


def resume(fleet: Fleet) -> Fleet:
    fleet.state = Fleet.STATE_ACTIVE
    fleet.save(update_fields=["state"])
    for device in fleet.devices.all():
        publish_worker_command(CHANNEL_DEVICES, action="spawn", device_id=str(device.id))
    _emit_state(fleet)

    from apps.system.notifications import push as notify

    notify(
        title=f"Fleet “{fleet.name}” resumed",
        message=f"{fleet.device_count} devices respawned",
        level="success",
        target_type="fleet",
        target_id=str(fleet.id),
    )

    return fleet


def teardown(fleet: Fleet) -> Fleet:
    """Mark the fleet retired, despawn all devices, keep rows for audit."""
    fleet.state = Fleet.STATE_TEARING_DOWN
    fleet.retired_at = timezone.now()
    fleet.save(update_fields=["state", "retired_at"])
    _emit_state(fleet)
    for device in fleet.devices.all():
        publish_worker_command(CHANNEL_DEVICES, action="despawn", device_id=str(device.id))
    fleet.state = Fleet.STATE_DELETED
    fleet.save(update_fields=["state"])
    _emit_state(fleet)

    from apps.system.notifications import push as notify

    notify(
        title=f"Fleet “{fleet.name}” torn down",
        message=f"All {fleet.device_count} devices despawned",
        level="error",
        target_type="fleet",
        target_id=str(fleet.id),
    )

    return fleet
