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
        # When a blueprint is supplied the device set (and model mix) comes
        # from there — both fields become optional on input.
        extra_kwargs = {
            "model_code": {"required": False, "default": ""},
            "device_count": {"required": False, "default": 0},
        }

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        blueprint = attrs.get("blueprint") or getattr(self.instance, "blueprint", None)
        model_code = attrs.get("model_code") or ""
        device_count = attrs.get("device_count", 0)
        if blueprint is None and (not model_code or device_count < 1):
            raise serializers.ValidationError(
                {
                    "model_code": (
                        "Either 'blueprint' or both 'model_code' and a positive "
                        "'device_count' must be provided."
                    ),
                }
            )
        return attrs

    def get_device_states(self, obj: Fleet) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in obj.devices.values("state").all():
            counts[row["state"]] = counts.get(row["state"], 0) + 1
        return counts
