from __future__ import annotations

from rest_framework import serializers

from .models import DeviceTemplate


class DeviceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceTemplate
        fields = (
            "id",
            "model_code",
            "model_display",
            "device_family",
            "hardware_capabilities",
            "default_config",
            "schema_version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
