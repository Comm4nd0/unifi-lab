from __future__ import annotations

from rest_framework import serializers

from .models import FlowRecord


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
