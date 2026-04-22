from __future__ import annotations

from django.contrib import admin

from .models import Fleet


@admin.register(Fleet)
class FleetAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "controller_target", "device_count", "created_at")
    list_filter = ("state",)
    search_fields = ("name",)
