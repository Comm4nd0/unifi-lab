from __future__ import annotations

from rest_framework import serializers

from .models import Fleet


class FleetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fleet
        fields = (
            "id",
            "name",
            "blueprint",
            "controller_target",
            "state",
            "device_count",
            "ramp_spec",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "state", "created_at", "updated_at")
