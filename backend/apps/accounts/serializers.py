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
