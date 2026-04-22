"""Readyz / version / metrics coverage."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_readyz_returns_200_with_db_ok():
    client = APIClient()
    resp = client.get("/api/v1/system/readyz/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["db"] == "ok"


@pytest.mark.django_db
def test_version_endpoint():
    client = APIClient()
    resp = client.get("/api/v1/system/version/")
    assert resp.status_code == 200
    assert resp.json()["version"] == "0.1.0"


@pytest.mark.django_db
def test_metrics_requires_admin(admin_user):
    anon = APIClient()
    assert anon.get("/api/v1/system/metrics/").status_code in (401, 403)

    authed = APIClient()
    authed.force_authenticate(admin_user)
    resp = authed.get("/api/v1/system/metrics/")
    assert resp.status_code == 200
    assert "uvl_virtual_devices_total" in resp.content.decode()
    assert resp["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_request_id_header_echoed(api_client):
    resp = api_client.get("/api/v1/system/health/")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp
    assert len(resp["X-Request-ID"]) >= 16  # UUID-ish


@pytest.mark.django_db
def test_client_supplied_request_id_is_preserved(api_client):
    resp = api_client.get(
        "/api/v1/system/health/",
        HTTP_X_REQUEST_ID="req-from-client",
    )
    assert resp["X-Request-ID"] == "req-from-client"
