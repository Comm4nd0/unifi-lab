from __future__ import annotations

from rest_framework import serializers

from .models import Blueprint


class BlueprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blueprint
        fields = (
            "id",
            "name",
            "source_yaml",
            "parsed_json",
            "version",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "parsed_json",
            "version",
            "created_by",
            "created_at",
            "updated_at",
        )
