"""Fleet event fan-out — every lifecycle transition hits the Channels layer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.devices.services import create_device
from apps.fleets.events import group_name
from apps.fleets.models import Fleet


@pytest.mark.django_db
def test_instantiate_fleet_emits_state_changed(api_client, controller_target):  # type: ignore[no-untyped-def]
    # Patch the imports at their call sites — services.py and tasks.py
    # bind ``publish_fleet_event`` locally, so patching the source module
    # doesn't intercept those calls.
    with (
        patch("apps.fleets.services.publish_fleet_event") as svc_pub,
        patch("apps.fleets.tasks.publish_fleet_event") as task_pub,
    ):
        resp = api_client.post(
            "/api/v1/fleets/",
            {
                "name": "live-1",
                "controller_target": str(controller_target.id),
                "model_code": "USW24P250",
                "device_count": 1,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        types = [call.args[1] for call in (*svc_pub.call_args_list, *task_pub.call_args_list)]
        # instantiate flips to ramping; eager-Celery task flips to active.
        assert "fleet.state_changed" in types


@pytest.mark.django_db
def test_pause_resume_emit_state_changed(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="pr",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    with patch("apps.fleets.services.publish_fleet_event") as pub:
        api_client.post(f"/api/v1/fleets/{fleet.id}/pause/")
        api_client.post(f"/api/v1/fleets/{fleet.id}/resume/")
    types = [call.args[1] for call in pub.call_args_list]
    assert types.count("fleet.state_changed") >= 2


@pytest.mark.django_db
def test_teardown_emits_state_changed(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="td",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    with patch("apps.fleets.services.publish_fleet_event") as pub:
        api_client.post(f"/api/v1/fleets/{fleet.id}/teardown/")
    types = [call.args[1] for call in pub.call_args_list]
    assert "fleet.state_changed" in types


@pytest.mark.django_db
def test_device_state_change_fans_out_event(controller_target):  # type: ignore[no-untyped-def]
    """The post_save signal should publish when a fleet-bound device changes state."""
    fleet = Fleet.objects.create(
        name="dev-sig",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
        fleet_id=str(fleet.id),
    )
    with patch("apps.devices.signals.publish_fleet_event") as pub:
        device.state = "adopted"
        device.save(update_fields=["state"])
    assert pub.called
    call = pub.call_args
    assert call.args[0] == str(fleet.id)
    assert call.args[1] == "device.state_changed"
    assert call.kwargs["state"] == "adopted"
    assert call.kwargs["device_id"] == str(device.id)


@pytest.mark.django_db
def test_device_without_fleet_does_not_emit(controller_target):  # type: ignore[no-untyped-def]
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    with patch("apps.devices.signals.publish_fleet_event") as pub:
        device.state = "adopted"
        device.save(update_fields=["state"])
    pub.assert_not_called()


@pytest.mark.django_db
def test_device_save_without_state_change_does_not_emit(controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="no-change",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    device = create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
        fleet_id=str(fleet.id),
    )
    with patch("apps.devices.signals.publish_fleet_event") as pub:
        # Touch an unrelated field.
        device.firmware_version = "8.3.42"
        device.save(update_fields=["firmware_version"])
    pub.assert_not_called()


def test_group_name_uses_dot_separator():
    # Sanity: Channels group-name validator rejects colons.
    assert group_name("abc-def") == "fleet.abc-def"
