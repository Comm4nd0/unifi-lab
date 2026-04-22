from __future__ import annotations

from django.contrib import admin

from .models import ControllerTarget


@admin.register(ControllerTarget)
class ControllerTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "health", "is_active", "last_verified_at")
    list_filter = ("kind", "health", "is_active")
    search_fields = ("name",)
    readonly_fields = ("health", "last_verified_at", "created_at", "updated_at")
