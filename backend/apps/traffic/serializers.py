from __future__ import annotations

import yaml
from rest_framework import serializers

from .models import FlowRecord, TrafficProfile


class FlowRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowRecord
        fields = (
            "id",
            "device",
            "protocol",
            "src_ip",
            "dst_ip",
            "src_port",
            "dst_port",
            "bytes_tx",
            "bytes_rx",
            "application",
            "blocked",
            "reported_at",
            "created_at",
        )
        read_only_fields = fields


def _parse_traffic_yaml(source: str) -> dict:
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise serializers.ValidationError({"source_yaml": f"YAML parse error: {exc}"}) from exc
    if not isinstance(data, dict):
        raise serializers.ValidationError(
            {"source_yaml": "Top-level traffic profile must be a mapping."}
        )
    if "flows" not in data:
        raise serializers.ValidationError({"source_yaml": "Profile must declare a 'flows' list."})
    if not isinstance(data["flows"], list):
        raise serializers.ValidationError({"source_yaml": "'flows' must be a list."})
    return data


class TrafficProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrafficProfile
        fields = (
            "id",
            "name",
            "description",
            "source_yaml",
            "parsed_json",
            "version",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "parsed_json", "version", "created_at", "updated_at")

    def create(self, validated_data):  # type: ignore[no-untyped-def]
        validated_data["parsed_json"] = _parse_traffic_yaml(validated_data["source_yaml"])
        validated_data["version"] = 1
        return super().create(validated_data)

    def update(self, instance: TrafficProfile, validated_data):  # type: ignore[no-untyped-def]
        if "source_yaml" in validated_data:
            validated_data["parsed_json"] = _parse_traffic_yaml(validated_data["source_yaml"])
            validated_data["version"] = instance.version + 1
        return super().update(instance, validated_data)
