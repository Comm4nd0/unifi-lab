"""Integration tests for fleet ramp behaviour + state transition task."""

from __future__ import annotations

import pytest

from apps.fleets.models import Fleet
from apps.fleets.tasks import transition_fleet_to_active


@pytest.mark.django_db
def test_fleet_ramping_transitions_to_active_via_eager_task(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "ramp-instant",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 2,
            "ramp_spec": {"mode": "all-at-once"},
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    fleet_id = resp.data["id"]
    # Under CELERY_TASK_ALWAYS_EAGER the transition task ran inline — the
    # row is already active by the time the caller re-fetches.
    fleet = Fleet.objects.get(pk=fleet_id)
    assert fleet.state == Fleet.STATE_ACTIVE


@pytest.mark.django_db
def test_ramp_spec_is_persisted(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "ramp-linear",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 3,
            "ramp_spec": {"mode": "linear", "devices_per_sec": 2},
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["ramp_spec"] == {"mode": "linear", "devices_per_sec": 2}


@pytest.mark.django_db
def test_transition_task_is_idempotent_off_ramping(controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="already-paused",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
        state=Fleet.STATE_PAUSED,
    )
    transition_fleet_to_active(str(fleet.id))
    fleet.refresh_from_db()
    # Should stay paused, not get flipped to active.
    assert fleet.state == Fleet.STATE_PAUSED


@pytest.mark.django_db
def test_transition_task_handles_missing_fleet():
    # Should not raise — just logs.
    transition_fleet_to_active("00000000-0000-0000-0000-000000000000")
