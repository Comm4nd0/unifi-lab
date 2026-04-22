"""FirmwareBlob — references an uploaded firmware image and its ingestion state."""

from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class FirmwareBlob(BaseModel):
    STATE_UPLOADED = "uploaded"
    STATE_INGESTING = "ingesting"
    STATE_READY = "ready"
    STATE_FAILED = "failed"
    STATE_CHOICES = [
        (STATE_UPLOADED, "Uploaded"),
        (STATE_INGESTING, "Ingesting"),
        (STATE_READY, "Ready"),
        (STATE_FAILED, "Failed"),
    ]

    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    size_bytes = models.BigIntegerField()
    model_codes = models.JSONField(default=list)
    version = models.CharField(max_length=64, blank=True, default="")
    storage_key = models.CharField(max_length=512, help_text="Filesystem path or S3 key")
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_UPLOADED)
    ingest_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.filename} ({self.version or 'unknown'})"
