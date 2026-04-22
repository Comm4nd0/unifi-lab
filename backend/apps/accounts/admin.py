from __future__ import annotations

from django.contrib import admin

from .models import ApiToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_admin", "is_staff", "is_active", "created_at")
    search_fields = ("email",)
    list_filter = ("is_admin", "is_staff", "is_active")


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "scopes", "expires_at", "last_used_at")
    search_fields = ("user__email", "name")
    readonly_fields = ("token_digest",)
