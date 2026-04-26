from __future__ import annotations

from rest_framework import serializers

from .models import ControllerTarget


class ControllerTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControllerTarget
        fields = (
            "id",
            "name",
            "kind",
            "inform_url",
            "api_url",
            "api_username",
            "api_password",
            "verify_tls",
            "is_active",
            "health",
            "last_verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "health", "last_verified_at", "created_at", "updated_at")
        extra_kwargs = {
            "api_password": {"write_only": True},
            "api_username": {"write_only": True},
            "inform_url": {"required": False, "allow_blank": True},
            "api_url": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        kind = attrs.get("kind") or (self.instance.kind if self.instance else None)
        if kind == ControllerTarget.KIND_VIRTUAL:
            # Virtual controllers don't need real URLs or credentials —
            # they're auto-populated on save by the viewset.
            attrs.setdefault("api_username", "virtual")
            attrs.setdefault("api_password", "virtual")
            attrs.setdefault("inform_url", "auto")
            attrs.setdefault("api_url", "auto")
            attrs.setdefault("verify_tls", False)
        else:
            # Real controllers require URLs
            if not attrs.get("inform_url") and not self.instance:
                raise serializers.ValidationError({"inform_url": "This field is required."})
            if not attrs.get("api_url") and not self.instance:
                raise serializers.ValidationError({"api_url": "This field is required."})
        return attrs


class ControllerSecretsSerializer(serializers.Serializer):
    """Input shape for POST /controllers/{id}/secrets — credential rotation."""

    api_username = serializers.CharField(required=False, allow_blank=False)
    api_password = serializers.CharField(required=False, allow_blank=False, write_only=True)
    inform_url = serializers.CharField(required=False, allow_blank=False)
    api_url = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        if not attrs:
            raise serializers.ValidationError("At least one secret field must be provided")
        return attrs
