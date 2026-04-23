"""POST /api/v1/devices/{id}/mark-adopted/ — worker callback endpoint."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.devices.models import VirtualDevice
from apps.devices.services import create_device

WORKER_TOKEN = "worker-secret-token"


@pytest.fixture
def device(controller_target):  # type: ignore[no-untyped-def]
    return create_device(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )


@pytest.mark.django_db
def test_mark_adopted_flips_state_when_bearer_matches(settings, device):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    resp = client.post(
        f"/api/v1/devices/{device.id}/mark-adopted/",
        HTTP_AUTHORIZATION=f"Bearer {WORKER_TOKEN}",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["state"] == VirtualDevice.STATE_ADOPTED
    device.refresh_from_db()
    assert device.state == VirtualDevice.STATE_ADOPTED
    assert device.last_heartbeat_at is not None


@pytest.mark.django_db
def test_mark_adopted_is_idempotent(settings, device):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    # First call adopts.
    client.post(
        f"/api/v1/devices/{device.id}/mark-adopted/",
        HTTP_AUTHORIZATION=f"Bearer {WORKER_TOKEN}",
    )
    device.refresh_from_db()
    first_hb = device.last_heartbeat_at
    # Second call should not re-write last_heartbeat_at.
    resp = client.post(
        f"/api/v1/devices/{device.id}/mark-adopted/",
        HTTP_AUTHORIZATION=f"Bearer {WORKER_TOKEN}",
    )
    assert resp.status_code == 200
    device.refresh_from_db()
    assert device.last_heartbeat_at == first_hb


@pytest.mark.django_db
def test_mark_adopted_rejects_wrong_bearer(settings, device):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    resp = client.post(
        f"/api/v1/devices/{device.id}/mark-adopted/",
        HTTP_AUTHORIZATION="Bearer something-else",
    )
    assert resp.status_code == 403
    device.refresh_from_db()
    assert device.state == VirtualDevice.STATE_PENDING


@pytest.mark.django_db
def test_mark_adopted_rejects_missing_authorization(settings, device):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    resp = client.post(f"/api/v1/devices/{device.id}/mark-adopted/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_mark_adopted_locked_when_worker_token_unset(settings, device):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = ""
    client = APIClient()
    # Even with a plausible bearer, empty server config means no-one passes.
    resp = client.post(
        f"/api/v1/devices/{device.id}/mark-adopted/",
        HTTP_AUTHORIZATION="Bearer anything",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_mark_adopted_rejects_user_jwt(settings, device, api_client):  # type: ignore[no-untyped-def]
    """Admin JWT shouldn't grant access to the worker-only endpoint."""
    settings.WORKER_TOKEN = WORKER_TOKEN
    # api_client fixture is JWT-authenticated as admin.
    resp = api_client.post(f"/api/v1/devices/{device.id}/mark-adopted/")
    assert resp.status_code == 403
