"""Controller target action endpoints: health-check, rotate secrets."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_health_check_runs_probe(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    body = resp.data
    # Probe against 127.0.0.1:443 in the test env will usually fail; accept any
    # of the deterministic outcomes.
    assert body["health"] in {"ok", "unreachable", "unknown"}
    assert body["last_verified_at"] is not None


@pytest.mark.django_db
def test_secrets_rotation_updates_fields(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        f"/api/v1/controllers/{controller_target.id}/secrets/",
        {"api_username": "rotated-user", "api_password": "rotated-secret"},
        format="json",
    )
    assert resp.status_code == 200
    controller_target.refresh_from_db()
    assert controller_target.api_username == "rotated-user"
    assert controller_target.api_password == "rotated-secret"


@pytest.mark.django_db
def test_secrets_rotation_rejects_empty(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        f"/api/v1/controllers/{controller_target.id}/secrets/",
        {},
        format="json",
    )
    assert resp.status_code == 400
