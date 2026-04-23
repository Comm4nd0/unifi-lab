from __future__ import annotations

from django.apps import AppConfig


class DevicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.devices"
    label = "devices"

    def ready(self) -> None:
        # Registers the post_save receiver that fans fleet events onto Channels.
        from . import signals  # noqa: F401
