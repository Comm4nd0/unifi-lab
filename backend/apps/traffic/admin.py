from __future__ import annotations

from django.contrib import admin

from .models import FlowRecord, TrafficProfile


@admin.register(FlowRecord)
class FlowRecordAdmin(admin.ModelAdmin):
    list_display = ("device", "protocol", "src_ip", "dst_ip", "application", "reported_at")
    list_filter = ("protocol", "blocked")
    search_fields = ("src_ip", "dst_ip", "application")
    readonly_fields = tuple(f.name for f in FlowRecord._meta.fields)


@admin.register(TrafficProfile)
class TrafficProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("parsed_json", "version", "created_at", "updated_at")
