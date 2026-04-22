from __future__ import annotations

from django.apps import AppConfig


class DeviceTemplatesConfig(AppConfig):
    """Device templates — metadata for each supported UniFi device model.

    Uses the label ``device_templates`` to avoid any collision with Django's
    internal use of the ``templates`` name.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.templates"
    label = "device_templates"
