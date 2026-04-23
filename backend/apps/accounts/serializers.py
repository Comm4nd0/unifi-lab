from __future__ import annotations

from rest_framework import serializers

from .models import ApiToken, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "is_admin", "created_at")
        read_only_fields = fields


class ApiTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiToken
        fields = ("id", "name", "scopes", "expires_at", "last_used_at", "created_at")
        read_only_fields = ("id", "last_used_at", "created_at")


class ApiTokenCreateSerializer(serializers.Serializer):
    """Input-only: captures ``name`` + ``scopes`` for a new token.

    The view generates the plaintext via ``ApiToken.generate`` and echoes
    it once in the response; the serializer itself never touches the
    plaintext so it can't accidentally round-trip.
    """

    name = serializers.CharField(max_length=255)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=[s for s, _ in ApiToken.SCOPE_CHOICES]),
        required=False,
        default=list,
    )

    def validate_scopes(self, value: list[str]) -> list[str]:
        # De-duplicate while preserving order so "read" + "read" → ["read"].
        seen: set[str] = set()
        out: list[str] = []
        for scope in value:
            if scope not in seen:
                seen.add(scope)
                out.append(scope)
        return out or ["read"]
