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
        }


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
