from __future__ import annotations

from django.contrib import admin

from .models import DeviceConfig, InformExchange, VirtualDevice


@admin.register(VirtualDevice)
class VirtualDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "mac_address",
        "model_code",
        "state",
        "fleet",
        "controller_target",
        "last_heartbeat_at",
    )
    list_filter = ("state", "model_code", "controller_target")
    search_fields = ("mac_address", "serial_number", "model_code")
    readonly_fields = ("inform_key_rotated_at", "last_heartbeat_at", "last_config_applied_at")


@admin.register(DeviceConfig)
class DeviceConfigAdmin(admin.ModelAdmin):
    list_display = ("device", "checksum", "applied_at")
    search_fields = ("device__mac_address", "checksum")


@admin.register(InformExchange)
class InformExchangeAdmin(admin.ModelAdmin):
    list_display = ("device", "exchange_type", "exchanged_at")
    list_filter = ("exchange_type",)
    search_fields = ("device__mac_address",)
    readonly_fields = ("device", "exchange_type", "payload_in", "payload_out", "exchanged_at")
