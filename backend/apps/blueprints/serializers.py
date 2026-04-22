from __future__ import annotations

from rest_framework import serializers

from .models import Blueprint
from .validator import parse_yaml, validate


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

    def _parse_and_validate(self, yaml_source: str) -> dict:
        parsed, err = parse_yaml(yaml_source)
        if err:
            raise serializers.ValidationError({"source_yaml": err})
        assert parsed is not None
        result = validate(parsed)
        if not result.valid:
            raise serializers.ValidationError(
                {
                    "source_yaml": [
                        f"{i.path}: {i.message}" for i in result.issues if i.severity == "error"
                    ]
                }
            )
        return parsed

    def create(self, validated_data):  # type: ignore[no-untyped-def]
        parsed = self._parse_and_validate(validated_data["source_yaml"])
        validated_data["parsed_json"] = parsed
        validated_data["version"] = 1
        validated_data.pop("created_by", None)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)

    def update(self, instance: Blueprint, validated_data):  # type: ignore[no-untyped-def]
        if "source_yaml" in validated_data:
            parsed = self._parse_and_validate(validated_data["source_yaml"])
            validated_data["parsed_json"] = parsed
            validated_data["version"] = instance.version + 1
        return super().update(instance, validated_data)


class BlueprintValidateSerializer(serializers.Serializer):
    source_yaml = serializers.CharField()

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        parsed, err = parse_yaml(attrs["source_yaml"])
        if err:
            attrs["_result"] = {
                "valid": False,
                "parsed": None,
                "issues": [{"severity": "error", "path": "<root>", "message": err}],
            }
            return attrs
        assert parsed is not None
        result = validate(parsed)
        attrs["_result"] = {
            "valid": result.valid,
            "parsed": result.parsed,
            "issues": [
                {"severity": i.severity, "path": i.path, "message": i.message}
                for i in result.issues
            ],
        }
        return attrs
