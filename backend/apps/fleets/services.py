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

from django.db import transaction
from django.utils import timezone

from apps.common.worker_commands import CHANNEL_DEVICES, publish_worker_command
from apps.devices.services import create_device

from .models import Fleet


def instantiate_fleet(fleet: Fleet) -> list[str]:
    """Materialise ``fleet`` into ``fleet.device_count`` virtual devices.

    Runs inside a transaction so a partial failure never leaves orphan
    rows or phantom Redis commands — spawn messages only fire after the
    insert commits.
    """
    device_ids: list[str] = []
    with transaction.atomic():
        fleet.state = Fleet.STATE_RAMPING
        fleet.save(update_fields=["state"])
        for _ in range(fleet.device_count):
            device = create_device(
                model_code=fleet.model_code,
                controller_target_id=str(fleet.controller_target_id),
                fleet_id=str(fleet.id),
            )
            device_ids.append(str(device.id))

    # Post-commit: ask the supervisor to spawn each device. Any Redis failure
    # falls back to the supervisor's startup poll catching them later.
    for device_id in device_ids:
        publish_worker_command(CHANNEL_DEVICES, action="spawn", device_id=device_id)
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
