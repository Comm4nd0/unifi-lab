from __future__ import annotations

from django.contrib import admin

from .models import FlowRecord


@admin.register(FlowRecord)
class FlowRecordAdmin(admin.ModelAdmin):
    list_display = ("device", "protocol", "src_ip", "dst_ip", "application", "reported_at")
    list_filter = ("protocol", "blocked")
    search_fields = ("src_ip", "dst_ip", "application")
    readonly_fields = tuple(f.name for f in FlowRecord._meta.fields)
