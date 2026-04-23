"""Simulate-action endpoints on VirtualDeviceViewSet."""

from __future__ import annotations

import pytest

from apps.devices.models import VirtualDevice
from apps.devices.services import create_device


@pytest.mark.django_db
def test_disconnect_flips_state_and_publishes_despawn(api_client, controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    device.state = VirtualDevice.STATE_HEARTBEAT
    device.save(update_fields=["state"])

    resp = api_client.post(f"/api/v1/devices/{device.id}/disconnect/")
    assert resp.status_code == 200, resp.data
    assert resp.data["state"] == VirtualDevice.STATE_DISCONNECTED

    device.refresh_from_db()
    assert device.state == VirtualDevice.STATE_DISCONNECTED


@pytest.mark.django_db
def test_reconnect_flips_to_pending(api_client, controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    device.state = VirtualDevice.STATE_DISCONNECTED
    device.save(update_fields=["state"])

    resp = api_client.post(f"/api/v1/devices/{device.id}/reconnect/")
    assert resp.status_code == 200, resp.data
    assert resp.data["state"] == VirtualDevice.STATE_PENDING
