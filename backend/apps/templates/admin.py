from __future__ import annotations

from django.contrib import admin

from .models import DeviceTemplate


@admin.register(DeviceTemplate)
class DeviceTemplateAdmin(admin.ModelAdmin):
    list_display = ("model_code", "model_display", "device_family", "schema_version")
    list_filter = ("device_family",)
    search_fields = ("model_code", "model_display")
