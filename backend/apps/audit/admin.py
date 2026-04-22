from __future__ import annotations

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "created_at")
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_id", "actor__email")
    readonly_fields = tuple(f.name for f in AuditLog._meta.fields)
