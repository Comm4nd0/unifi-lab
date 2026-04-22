from __future__ import annotations

from rest_framework import serializers

from .models import DeviceConfig, InformExchange, VirtualDevice


class VirtualDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VirtualDevice
        fields = (
            "id",
            "mac_address",
            "serial_number",
            "model_code",
            "firmware_version",
            "state",
            "controller_target",
            "fleet",
            "last_heartbeat_at",
            "last_config_applied_at",
            "created_at",
            "updated_at",
        )
        # MAC and serial are server-generated. Clients POST model_code +
        # optional controller_target/fleet; everything else is read-only.
        read_only_fields = (
            "id",
            "mac_address",
            "serial_number",
            "state",
            "last_heartbeat_at",
            "last_config_applied_at",
            "created_at",
            "updated_at",
        )


class DeviceConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceConfig
        fields = ("id", "device", "applied_config", "checksum", "applied_at", "created_at")
        read_only_fields = fields


class InformExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InformExchange
        fields = (
            "id",
            "device",
            "exchange_type",
            "payload_in",
            "payload_out",
            "exchanged_at",
            "created_at",
        )
        read_only_fields = fields
