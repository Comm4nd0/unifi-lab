"""Integration tests for the devices API — Phase 0 smoke coverage."""

from __future__ import annotations

import pytest

from apps.devices.models import VirtualDevice
from apps.devices.services import create_device


@pytest.mark.django_db
def test_create_device_returns_201(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/devices/",
        {
            "model_code": "USW24P250",
            "firmware_version": "8.3.42",
            "controller_target": str(controller_target.id),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["model_code"] == "USW24P250"
    assert resp.data["state"] == VirtualDevice.STATE_PENDING


@pytest.mark.django_db
def test_retrieve_device(api_client, controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    resp = api_client.get(f"/api/v1/devices/{device.id}/")
    assert resp.status_code == 200, resp.data
    assert resp.data["mac_address"] == device.mac_address


@pytest.mark.django_db
def test_inform_log_endpoint(api_client, controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    resp = api_client.get(f"/api/v1/devices/{device.id}/inform-log/")
    assert resp.status_code == 200
    assert resp.data["count"] == 0
