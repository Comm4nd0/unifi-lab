from __future__ import annotations

from django.contrib import admin

from .models import Blueprint


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
