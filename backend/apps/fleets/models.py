"""Fleet — a named collection of virtual devices provisioned together."""

from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Fleet(BaseModel):
    STATE_CREATING = "creating"
    STATE_RAMPING = "ramping"
    STATE_ACTIVE = "active"
    STATE_PAUSED = "paused"
    STATE_TEARING_DOWN = "tearing_down"
    STATE_DELETED = "deleted"
    STATE_CHOICES = [
        (STATE_CREATING, "Creating"),
        (STATE_RAMPING, "Ramping"),
        (STATE_ACTIVE, "Active"),
        (STATE_PAUSED, "Paused"),
        (STATE_TEARING_DOWN, "Tearing down"),
        (STATE_DELETED, "Deleted"),
    ]

    name = models.CharField(max_length=255, unique=True)
    blueprint = models.ForeignKey(
        "blueprints.Blueprint",
        on_delete=models.PROTECT,
        related_name="fleets",
        null=True,
        blank=True,
    )
    controller_target = models.ForeignKey(
        "controllers.ControllerTarget",
        on_delete=models.PROTECT,
        related_name="fleets",
    )
    model_code = models.CharField(
        max_length=32,
        default="USW24P250",
        help_text="Model every device in this fleet gets. Phase 2 blueprint support will add per-device mixing.",
    )
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_CREATING)
    device_count = models.PositiveIntegerField(default=0)
    ramp_spec = models.JSONField(default=dict, blank=True)
    auto_adopt = models.BooleanField(default=False)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name
