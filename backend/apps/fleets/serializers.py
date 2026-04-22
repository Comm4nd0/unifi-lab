from __future__ import annotations

from rest_framework import serializers

from .models import Fleet


class FleetSerializer(serializers.ModelSerializer):
    device_states = serializers.SerializerMethodField()

    class Meta:
        model = Fleet
        fields = (
            "id",
            "name",
            "blueprint",
            "controller_target",
            "model_code",
            "state",
            "device_count",
            "ramp_spec",
            "auto_adopt",
            "retired_at",
            "device_states",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "state",
            "retired_at",
            "device_states",
            "created_at",
            "updated_at",
        )

    def get_device_states(self, obj: Fleet) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in obj.devices.values("state").all():
            counts[row["state"]] = counts.get(row["state"], 0) + 1
        return counts
