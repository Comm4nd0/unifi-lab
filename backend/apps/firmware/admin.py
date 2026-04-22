from __future__ import annotations

from django.contrib import admin

from .models import FirmwareBlob


@admin.register(FirmwareBlob)
class FirmwareBlobAdmin(admin.ModelAdmin):
    list_display = ("filename", "version", "state", "size_bytes", "created_at")
    list_filter = ("state",)
    search_fields = ("filename", "sha256", "version")
