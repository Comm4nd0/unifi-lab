"""DRF serialisers. Presentation only — the reasoning lives in services."""

from __future__ import annotations

from rest_framework import serializers

from netsim.models import Client, Device, Flow, Link, Network, Port, Site
from netsim.services import create_device, create_link
from simcore.catalog import CATALOG
from simcore.topology import LinkError


class SiteSerializer(serializers.ModelSerializer):
    device_count = serializers.IntegerField(source="devices.count", read_only=True)
    client_count = serializers.IntegerField(source="clients.count", read_only=True)

    class Meta:
        model = Site
        fields = [
            "id", "name", "description", "stp_mode",
            "wan_download_mbps", "wan_upload_mbps",
            "device_count", "client_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = ["id", "site", "name", "vlan_id", "subnet", "purpose", "isolated"]


class PortSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)  # type: ignore[assignment]
    media = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    max_speed_mbps = serializers.SerializerMethodField()
    poe_out = serializers.SerializerMethodField()
    poe_max_w = serializers.SerializerMethodField()
    poe_in = serializers.SerializerMethodField()
    link_id = serializers.SerializerMethodField()
    device_name = serializers.CharField(source="device.name", read_only=True)

    class Meta:
        model = Port
        fields = [
            "id", "device", "device_name", "index", "name", "label", "enabled",
            "poe_enabled", "bpdu_guard", "speed_override", "native_network",
            "media", "role", "max_speed_mbps", "poe_out", "poe_max_w", "poe_in",
            "link_id",
        ]
        read_only_fields = ["device", "index"]

    def get_media(self, obj: Port) -> str:
        return obj.spec.media

    def get_role(self, obj: Port) -> str:
        return obj.spec.role

    def get_max_speed_mbps(self, obj: Port) -> int:
        return obj.spec.speed_mbps

    def get_poe_out(self, obj: Port) -> str | None:
        return obj.spec.poe_out

    def get_poe_max_w(self, obj: Port) -> float:
        return obj.spec.poe_max_w

    def get_poe_in(self, obj: Port) -> str | None:
        return obj.spec.poe_in

    def get_link_id(self, obj: Port) -> int | None:
        link = getattr(obj, "link_a", None) or getattr(obj, "link_b", None)
        return link.pk if link else None


class DeviceSerializer(serializers.ModelSerializer):
    ports = PortSerializer(many=True, read_only=True)
    model_name = serializers.SerializerMethodField()
    line = serializers.SerializerMethodField()
    short = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            "id", "site", "name", "model", "model_name", "short", "line", "mac", "ip",
            "x", "y", "enabled", "stp_enabled", "stp_priority", "note", "ports",
        ]
        read_only_fields = ["mac"]
        extra_kwargs = {"name": {"required": False}}

    def get_model_name(self, obj: Device) -> str:
        return obj.spec.name

    def get_line(self, obj: Device) -> str:
        return obj.spec.line

    def get_short(self, obj: Device) -> str:
        return obj.spec.short

    def validate_model(self, value: str) -> str:
        if value not in CATALOG:
            raise serializers.ValidationError(f"{value} is not in the UniFi catalogue.")
        return value

    def create(self, validated_data: dict) -> Device:
        site = validated_data.pop("site")
        model = validated_data.pop("model")
        name = validated_data.pop("name", None)
        return create_device(site, model, name=name, **validated_data)


class LinkSerializer(serializers.ModelSerializer):
    a_label = serializers.SerializerMethodField()
    b_label = serializers.SerializerMethodField()
    a_device = serializers.IntegerField(source="a_port.device_id", read_only=True)
    b_device = serializers.IntegerField(source="b_port.device_id", read_only=True)

    class Meta:
        model = Link
        fields = [
            "id", "site", "a_port", "b_port", "a_device", "b_device",
            "a_label", "b_label", "cable", "enabled",
        ]

    def get_a_label(self, obj: Link) -> str:
        return f"{obj.a_port.device.name} · {obj.a_port.label}"

    def get_b_label(self, obj: Link) -> str:
        return f"{obj.b_port.device.name} · {obj.b_port.label}"

    def create(self, validated_data: dict) -> Link:
        try:
            return create_link(
                validated_data["site"],
                validated_data["a_port"],
                validated_data["b_port"],
                validated_data.get("cable", "cat6"),
            )
        except LinkError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class ClientSerializer(serializers.ModelSerializer):
    device_name = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id", "site", "name", "kind", "category", "mac", "ip", "port",
            "access_point", "network", "down_mbps", "up_mbps", "rssi_dbm",
            "device_name",
        ]
        read_only_fields = ["mac"]

    def get_device_name(self, obj: Client) -> str | None:
        if obj.port is not None:
            return obj.port.device.name
        if obj.access_point is not None:
            return obj.access_point.name
        return None

    def validate(self, attrs: dict) -> dict:
        kind = attrs.get("kind", getattr(self.instance, "kind", "wired"))
        if kind == "wireless" and attrs.get("port"):
            raise serializers.ValidationError(
                {"port": "A wireless client attaches to an access point, not a port."}
            )
        return attrs

    def create(self, validated_data: dict) -> Client:
        from simcore.builder import generate_mac

        client = super().create(validated_data)
        if not client.mac:
            client.mac = generate_mac(f"client-{client.pk}")
            client.save(update_fields=["mac"])
        return client


class FlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flow
        fields = [
            "id", "site", "name", "enabled", "protocol", "mbps", "burstiness",
            "src_kind", "src_client", "src_device",
            "dst_kind", "dst_client", "dst_device",
        ]
