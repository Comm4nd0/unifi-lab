"""Audit-log middleware writes rows for state-changing requests."""

from __future__ import annotations

import pytest

from apps.audit.models import AuditLog


@pytest.mark.django_db
def test_post_writes_audit_row(api_client, controller_target):  # type: ignore[no-untyped-def]
    AuditLog.objects.all().delete()
    resp = api_client.post(
        "/api/v1/devices/",
        {"model_code": "USW24P250", "controller_target": str(controller_target.id)},
        format="json",
    )
    assert resp.status_code == 201
    rows = list(AuditLog.objects.all())
    assert len(rows) == 1
    entry = rows[0]
    assert entry.action == "POST /api/v1/devices/"
    assert entry.target_type == "devices"
    assert entry.metadata["status_code"] == 201
    assert "request_id" in entry.metadata


@pytest.mark.django_db
def test_get_does_not_audit(api_client):
    AuditLog.objects.all().delete()
    resp = api_client.get("/api/v1/devices/")
    assert resp.status_code == 200
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_unauthenticated_post_does_not_audit(controller_target):  # type: ignore[no-untyped-def]
    from rest_framework.test import APIClient

    AuditLog.objects.all().delete()
    client = APIClient()
    resp = client.post(
        "/api/v1/devices/",
        {"model_code": "USW24P250", "controller_target": str(controller_target.id)},
        format="json",
    )
    assert resp.status_code in (401, 403)
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_delete_captures_target_id(api_client, controller_target):  # type: ignore[no-untyped-def]
    from apps.devices.services import create_device

    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    AuditLog.objects.all().delete()
    resp = api_client.delete(f"/api/v1/devices/{device.id}/")
    assert resp.status_code in (200, 204)
    row = AuditLog.objects.get()
    assert row.target_type == "devices"
    assert row.target_id == str(device.id)
