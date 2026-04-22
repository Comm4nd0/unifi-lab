"""DeviceTemplate — the canonical profile for a given UniFi device model."""

from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class DeviceTemplate(BaseModel):
    FAMILY_AP = "ap"
    FAMILY_SWITCH = "switch"
    FAMILY_GATEWAY = "gateway"
    FAMILY_OTHER = "other"
    FAMILY_CHOICES = [
        (FAMILY_AP, "Access point"),
        (FAMILY_SWITCH, "Switch"),
        (FAMILY_GATEWAY, "Gateway"),
        (FAMILY_OTHER, "Other"),
    ]

    model_code = models.CharField(max_length=32, unique=True, db_index=True)
    model_display = models.CharField(max_length=200)
    device_family = models.CharField(max_length=16, choices=FAMILY_CHOICES)
    hardware_capabilities = models.JSONField(default=dict)
    default_config = models.JSONField(default=dict)
    schema_version = models.CharField(max_length=32, default="uvl-template/v1")

    class Meta:
        ordering = ("model_code",)

    def __str__(self) -> str:
        return f"{self.model_code} ({self.model_display})"
