"""Seed the DB with a minimum viable set of rows so the UI is non-empty.

Creates:
- An admin user (from UVL_ADMIN_EMAIL / UVL_ADMIN_PASSWORD env or defaults).
- A "Localhost Lab" ControllerTarget pointing at 127.0.0.1 (placeholder creds).
- A handful of DeviceTemplates (USW24P250, U6-Pro, UDR) so the device-create
  form has a model list.

Idempotent — re-running it updates missing rows without duplicating.
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.controllers.models import ControllerTarget
from apps.templates.models import DeviceTemplate

SAMPLE_TEMPLATES = [
    {
        "model_code": "USW24P250",
        "model_display": "UniFi Switch 24 PoE (250W)",
        "device_family": DeviceTemplate.FAMILY_SWITCH,
    },
    {
        "model_code": "U6-Pro",
        "model_display": "U6 Pro Access Point",
        "device_family": DeviceTemplate.FAMILY_AP,
    },
    {
        "model_code": "UDR",
        "model_display": "UniFi Dream Router",
        "device_family": DeviceTemplate.FAMILY_GATEWAY,
    },
]


class Command(BaseCommand):
    help = "Seed the database with example controller target, device templates, and admin user."

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        User = get_user_model()

        email = os.environ.get("UVL_ADMIN_EMAIL", "admin@uvl.local")
        password = os.environ.get("UVL_ADMIN_PASSWORD", "change-me-on-first-login")
        if not email or not password:
            raise CommandError("UVL_ADMIN_EMAIL and UVL_ADMIN_PASSWORD must be set")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"is_admin": True, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"created admin {email}"))
        else:
            self.stdout.write(f"admin {email} already exists")

        for tmpl in SAMPLE_TEMPLATES:
            obj, tmpl_created = DeviceTemplate.objects.update_or_create(
                model_code=tmpl["model_code"],
                defaults={
                    "model_display": tmpl["model_display"],
                    "device_family": tmpl["device_family"],
                },
            )
            verb = "created" if tmpl_created else "updated"
            self.stdout.write(f"{verb} template {obj.model_code}")

        _, ctrl_created = ControllerTarget.objects.get_or_create(
            name="Localhost Lab",
            defaults={
                "kind": ControllerTarget.KIND_UOS_SERVER,
                "inform_url": "https://127.0.0.1:443",
                "api_url": "https://127.0.0.1:443/api",
                "api_username": "admin",
                "api_password": "replace-me",
                "verify_tls": False,
            },
        )
        if ctrl_created:
            self.stdout.write(self.style.SUCCESS("created controller 'Localhost Lab'"))
        else:
            self.stdout.write("controller 'Localhost Lab' already exists")
