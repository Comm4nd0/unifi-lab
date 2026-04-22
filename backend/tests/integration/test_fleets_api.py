"""Fleets CRUD + action endpoints."""

from __future__ import annotations

import pytest

from apps.devices.models import VirtualDevice
from apps.fleets.models import Fleet


@pytest.mark.django_db
def test_create_fleet_spawns_n_devices(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "E2E Fleet",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 4,
            "auto_adopt": False,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    fleet_id = resp.data["id"]
    assert resp.data["state"] == Fleet.STATE_RAMPING
    assert VirtualDevice.objects.filter(fleet_id=fleet_id).count() == 4
    assert resp.data["device_states"] == {"pending": 4}


@pytest.mark.django_db
def test_pause_and_resume_flip_state(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="Pause Fleet",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    resp = api_client.post(f"/api/v1/fleets/{fleet.id}/pause/")
    assert resp.status_code == 200
    assert resp.data["state"] == Fleet.STATE_PAUSED

    resp = api_client.post(f"/api/v1/fleets/{fleet.id}/resume/")
    assert resp.status_code == 200
    assert resp.data["state"] == Fleet.STATE_ACTIVE


@pytest.mark.django_db
def test_teardown_returns_202_and_marks_deleted(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="Teardown Fleet",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    resp = api_client.post(f"/api/v1/fleets/{fleet.id}/teardown/")
    assert resp.status_code == 202
    assert resp.data["state"] == Fleet.STATE_DELETED
    assert resp.data["retired_at"] is not None


@pytest.mark.django_db
def test_fleet_detail_includes_device_state_breakdown(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "Breakdown Fleet",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 3,
        },
        format="json",
    )
    fleet_id = resp.data["id"]
    # Flip one device to a different state to prove the aggregation works.
    VirtualDevice.objects.filter(fleet_id=fleet_id).first().__class__.objects.filter(
        fleet_id=fleet_id
    ).update()  # no-op, kept for clarity
    one = VirtualDevice.objects.filter(fleet_id=fleet_id).first()
    assert one is not None
    one.state = VirtualDevice.STATE_ADOPTED
    one.save(update_fields=["state"])

    resp = api_client.get(f"/api/v1/fleets/{fleet_id}/")
    assert resp.status_code == 200
    assert resp.data["device_states"] == {"pending": 2, "adopted": 1}
