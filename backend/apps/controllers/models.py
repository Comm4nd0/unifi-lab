"""ControllerTarget — a UniFi OS Server we can adopt virtual devices into.

Credentials are Fernet-encrypted at rest. Never log decrypted fields.
"""

from __future__ import annotations

from django.db import models

from apps.common.fields import EncryptedTextField
from apps.common.models import BaseModel


class ControllerTarget(BaseModel):
    KIND_UOS_SERVER = "uos-server"
    KIND_LEGACY = "legacy-network"
    KIND_VIRTUAL = "virtual"
    KIND_CHOICES = [
        (KIND_UOS_SERVER, "UniFi OS Server"),
        (KIND_LEGACY, "Legacy Network"),
        (KIND_VIRTUAL, "Virtual UDM (built-in)"),
    ]

    HEALTH_OK = "ok"
    HEALTH_AUTH_FAILED = "auth-failed"
    HEALTH_UNREACHABLE = "unreachable"
    HEALTH_UNKNOWN = "unknown"
    HEALTH_CHOICES = [
        (HEALTH_OK, "OK"),
        (HEALTH_AUTH_FAILED, "Auth failed"),
        (HEALTH_UNREACHABLE, "Unreachable"),
        (HEALTH_UNKNOWN, "Unknown"),
    ]

    name = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_UOS_SERVER)
    inform_url = EncryptedTextField()
    api_url = EncryptedTextField()
    api_username = EncryptedTextField()
    api_password = EncryptedTextField()
    verify_tls = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    health = models.CharField(max_length=32, choices=HEALTH_CHOICES, default=HEALTH_UNKNOWN)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
