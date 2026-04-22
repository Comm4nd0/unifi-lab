"""Device models — the heart of Phase 0.

VirtualDevice is the Django-side record of a simulated device. The asyncio
engine worker reads it to know what to instantiate; it never writes through
Django ORM. InformExchange is worker-owned — defined here for admin/read
access but writes happen over SQLAlchemy async in ``engine/db/``.
"""

from __future__ import annotations

from django.db import models

from apps.common.fields import EncryptedTextField
from apps.common.models import BaseModel


class VirtualDevice(BaseModel):
    STATE_PENDING = "pending"
    STATE_KEY_EXCHANGE = "key_exchange"
    STATE_HEARTBEAT = "heartbeat"
    STATE_CONFIG_APPLY = "config_apply"
    STATE_ADOPTED = "adopted"
    STATE_DISCONNECTED = "disconnected"
    STATE_ERROR = "error"
    STATE_CHOICES = [
        (STATE_PENDING, "Pending"),
        (STATE_KEY_EXCHANGE, "Key exchange"),
        (STATE_HEARTBEAT, "Heartbeat"),
        (STATE_CONFIG_APPLY, "Config apply"),
        (STATE_ADOPTED, "Adopted"),
        (STATE_DISCONNECTED, "Disconnected"),
        (STATE_ERROR, "Error"),
    ]

    mac_address = models.CharField(max_length=17, unique=True, db_index=True)
    serial_number = models.CharField(max_length=64, unique=True, db_index=True)
    model_code = models.CharField(max_length=32)
    firmware_version = models.CharField(max_length=32, blank=True, default="")
    hostname = models.CharField(max_length=64, blank=True, default="")

    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_PENDING)
    inform_key = EncryptedTextField(blank=True, default="")
    inform_key_rotated_at = models.DateTimeField(null=True, blank=True)

    controller_target = models.ForeignKey(
        "controllers.ControllerTarget",
        on_delete=models.PROTECT,
        related_name="devices",
        null=True,
        blank=True,
    )
    fleet = models.ForeignKey(
        "fleets.Fleet",
        on_delete=models.SET_NULL,
        related_name="devices",
        null=True,
        blank=True,
    )

    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_config_applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["controller_target", "state"]),
        ]

    def __str__(self) -> str:
        return f"{self.model_code} {self.mac_address} [{self.state}]"


class DeviceConfig(BaseModel):
    device = models.ForeignKey(VirtualDevice, on_delete=models.CASCADE, related_name="configs")
    applied_config = models.JSONField()
    checksum = models.CharField(max_length=64, db_index=True)
    applied_at = models.DateTimeField()

    class Meta:
        ordering = ("-applied_at",)


class InformExchange(BaseModel):
    """Worker-owned: the engine writes rows via SQLAlchemy async; Django reads only.

    A drift-detection test in ``tests/contract/`` verifies the SQLAlchemy
    model and this Django model stay in sync.
    """

    TYPE_ADOPT = "adopt"
    TYPE_HEARTBEAT = "heartbeat"
    TYPE_CONFIG_PUSH = "config_push"
    TYPE_STATS = "stats"
    TYPE_ERROR = "error"
    TYPE_CHOICES = [
        (TYPE_ADOPT, "Adopt"),
        (TYPE_HEARTBEAT, "Heartbeat"),
        (TYPE_CONFIG_PUSH, "Config push"),
        (TYPE_STATS, "Stats"),
        (TYPE_ERROR, "Error"),
    ]

    device = models.ForeignKey(
        VirtualDevice, on_delete=models.CASCADE, related_name="inform_exchanges"
    )
    exchange_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    payload_in = models.JSONField(null=True, blank=True)
    payload_out = models.JSONField(null=True, blank=True)
    exchanged_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-exchanged_at",)
        indexes = [models.Index(fields=["device", "-exchanged_at"])]
