"""Device-state signal fan-out onto the fleet's channel group.

When a VirtualDevice's state changes, we publish a ``device.state_changed``
event to ``fleet.{fleet_id}`` so the fleet detail UI can update without
polling. Only fires when the row is attached to a fleet and the state
actually changed (not on unrelated updates).
"""

from __future__ import annotations

from django.db.models.signals import post_init, post_save
from django.dispatch import receiver

from apps.fleets.events import publish_fleet_event

from .models import VirtualDevice


@receiver(post_init, sender=VirtualDevice)
def _remember_initial_state(sender, instance: VirtualDevice, **kwargs) -> None:  # type: ignore[no-untyped-def]
    # Cache the loaded state so post_save can tell whether it changed.
    instance._prev_state = instance.state  # type: ignore[attr-defined]


@receiver(post_save, sender=VirtualDevice)
def _publish_state_change(sender, instance: VirtualDevice, created: bool, **kwargs) -> None:  # type: ignore[no-untyped-def]
    prev = getattr(instance, "_prev_state", None)
    instance._prev_state = instance.state  # type: ignore[attr-defined]
    if not instance.fleet_id:
        return
    if not created and prev == instance.state:
        return
    publish_fleet_event(
        str(instance.fleet_id),
        "device.state_changed",
        device_id=str(instance.id),
        mac_address=instance.mac_address,
        hostname=instance.hostname,
        state=instance.state,
    )
