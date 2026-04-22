from __future__ import annotations

from rest_framework import serializers

from .models import FirmwareBlob


class FirmwareBlobSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirmwareBlob
        fields = (
            "id",
            "filename",
            "sha256",
            "size_bytes",
            "model_codes",
            "version",
            "state",
            "ingest_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "state", "ingest_error", "created_at", "updated_at")
