"""Celery tasks for fleet lifecycle post-processing.

Instantiation is synchronous on the Django side — it only writes rows and
publishes work. State transitions that depend on the worker's ramp-spec
timing run as delayed Celery tasks with ``countdown`` so they fire after
the ramp completes. In dev (``CELERY_TASK_ALWAYS_EAGER``) they run inline.
"""

from __future__ import annotations

import logging

from celery import shared_task

from .events import publish_fleet_event
from .models import Fleet

log = logging.getLogger("uvl.fleets.tasks")


@shared_task(name="fleets.transition_to_active")
def transition_fleet_to_active(fleet_id: str) -> None:
    """Flip a fleet from 'ramping' to 'active' once the ramp budget is up.

    Idempotent — if the fleet is already past ramping (e.g. operator paused
    it or tore it down mid-ramp), we leave it alone.
    """
    try:
        fleet = Fleet.objects.get(pk=fleet_id)
    except Fleet.DoesNotExist:
        log.warning("transition_to_active.fleet_missing", extra={"fleet_id": fleet_id})
        return
    if fleet.state != Fleet.STATE_RAMPING:
        log.info(
            "transition_to_active.skipped",
            extra={"fleet_id": fleet_id, "state": fleet.state},
        )
        return
    fleet.state = Fleet.STATE_ACTIVE
    fleet.save(update_fields=["state"])
    publish_fleet_event(
        str(fleet.id),
        "fleet.state_changed",
        state=fleet.state,
        device_count=fleet.device_count,
    )
    log.info("transition_to_active.done", extra={"fleet_id": fleet_id})
