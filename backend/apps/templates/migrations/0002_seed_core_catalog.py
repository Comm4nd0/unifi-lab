"""Seed the DeviceTemplate catalog with a representative cross-section of
UniFi models.

Every environment — dev, test, prod — gets the same canonical list the
blueprint editor uses for its palette. Idempotent: re-runs
(e.g. sqlmigrate replays) overwrite ``model_display`` / ``device_family``
on an existing ``model_code`` but never duplicate.

This migration intentionally includes broadly-released models as of
late-2025. Newer SKUs land as future migrations.
"""

from __future__ import annotations

from django.db import migrations

CATALOG = [
    # --- Gateways ----------------------------------------------------------
    ("UDR", "UniFi Dream Router", "gateway"),
    ("UDM-Pro", "UniFi Dream Machine Pro", "gateway"),
    ("UDM-SE", "UniFi Dream Machine SE", "gateway"),
    ("UDM-Pro-Max", "UniFi Dream Machine Pro Max", "gateway"),
    ("UXG-Pro", "UniFi Next-gen Gateway Pro", "gateway"),
    ("UXG-Max", "UniFi Next-gen Gateway Max", "gateway"),
    ("UXG-Lite", "UniFi Next-gen Gateway Lite", "gateway"),
    # --- Switches ----------------------------------------------------------
    ("USW-Lite-8-PoE", "UniFi Switch Lite 8 PoE", "switch"),
    ("USW-Lite-16-PoE", "UniFi Switch Lite 16 PoE", "switch"),
    ("USW-Flex-2.5G-8", "UniFi Switch Flex 2.5G 8", "switch"),
    ("USW24P250", "UniFi Switch 24 PoE (250W)", "switch"),
    ("USW-Pro-24-PoE", "UniFi Switch Pro 24 PoE", "switch"),
    ("USW-Pro-Max-24-PoE", "UniFi Switch Pro Max 24 PoE", "switch"),
    ("USW-48-PoE", "UniFi Switch 48 PoE", "switch"),
    ("USW-Pro-48-PoE", "UniFi Switch Pro 48 PoE", "switch"),
    ("USW-Enterprise-24-PoE", "UniFi Switch Enterprise 24 PoE", "switch"),
    ("USW-Enterprise-48-PoE", "UniFi Switch Enterprise 48 PoE", "switch"),
    ("USW-Aggregation", "UniFi Switch Aggregation", "switch"),
    # --- Access points -----------------------------------------------------
    ("U6-Lite", "U6 Lite Access Point", "ap"),
    ("U6-Pro", "U6 Pro Access Point", "ap"),
    ("U6-LR", "U6 Long-Range Access Point", "ap"),
    ("U6-Mesh", "U6 Mesh Access Point", "ap"),
    ("U6-IW", "U6 In-Wall Access Point", "ap"),
    ("U6-Enterprise", "U6 Enterprise Access Point", "ap"),
    ("U7-Pro", "U7 Pro Access Point", "ap"),
    ("U7-Pro-Max", "U7 Pro Max Access Point", "ap"),
    ("U7-Outdoor", "U7 Outdoor Access Point", "ap"),
    ("UAP-AC-Pro", "UAP AC Pro (legacy AC Wave 2)", "ap"),
]


def seed_catalog(apps, schema_editor):  # type: ignore[no-untyped-def]
    DeviceTemplate = apps.get_model("device_templates", "DeviceTemplate")
    for model_code, model_display, device_family in CATALOG:
        DeviceTemplate.objects.update_or_create(
            model_code=model_code,
            defaults={
                "model_display": model_display,
                "device_family": device_family,
            },
        )


def unseed_catalog(apps, schema_editor):  # type: ignore[no-untyped-def]
    # Reverse is a no-op: unseeding could nuke templates referenced by real
    # VirtualDevice rows, which would cascade badly. On rollback we keep
    # the catalog — the forward migration is idempotent, so re-applying
    # simply reconciles it.
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("device_templates", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, unseed_catalog),
    ]
