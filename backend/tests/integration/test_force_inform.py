"""Force-inform endpoint + worker command publisher."""

from __future__ import annotations

import pytest

from apps.devices.services import create_device


@pytest.mark.django_db
def test_force_inform_returns_202(api_client, controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    resp = api_client.post(f"/api/v1/devices/{device.id}/force-inform/")
    assert resp.status_code == 202, resp.data
    body = resp.data
    assert body["accepted"] is True
    assert body["device_id"] == str(device.id)
