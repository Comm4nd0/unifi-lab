"""Worker heartbeat endpoint + status readback.

The worker POSTs to ``/api/v1/system/worker-heartbeat/`` every 30s
carrying its bearer token; authenticated dashboard users read the
latest beat via ``/api/v1/system/worker-status/``. Storage goes
through Django's cache abstraction — LocMemCache in dev/tests,
redis-backed in prod. Tests clear the cache between runs so state
from one test doesn't leak into another.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.system.views import WORKER_HEARTBEAT_KEY

WORKER_TOKEN = "worker-secret-token"


@pytest.fixture(autouse=True)
def _clear_cache():  # type: ignore[no-untyped-def]
    cache.delete(WORKER_HEARTBEAT_KEY)
    yield
    cache.delete(WORKER_HEARTBEAT_KEY)


@pytest.mark.django_db
def test_worker_heartbeat_records_when_bearer_matches(settings):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    resp = client.post(
        "/api/v1/system/worker-heartbeat/",
        {"pid": 1234, "version": "0.1.0"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {WORKER_TOKEN}",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["recorded"] is True
    stored = cache.get(WORKER_HEARTBEAT_KEY)
    assert stored is not None
    assert stored["metadata"] == {"pid": 1234, "version": "0.1.0"}


@pytest.mark.django_db
def test_worker_heartbeat_rejects_wrong_bearer(settings):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    client = APIClient()
    resp = client.post(
        "/api/v1/system/worker-heartbeat/",
        {},
        format="json",
        HTTP_AUTHORIZATION="Bearer wrong",
    )
    assert resp.status_code == 403
    assert cache.get(WORKER_HEARTBEAT_KEY) is None


@pytest.mark.django_db
def test_worker_heartbeat_rejects_user_jwt(settings, api_client):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    resp = api_client.post("/api/v1/system/worker-heartbeat/", {}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_worker_status_reports_alive_after_heartbeat(settings, api_client):  # type: ignore[no-untyped-def]
    settings.WORKER_TOKEN = WORKER_TOKEN
    # Record a heartbeat first.
    worker = APIClient()
    worker.post(
        "/api/v1/system/worker-heartbeat/",
        {"pid": 4242},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {WORKER_TOKEN}",
    )
    # Dashboard reads it back.
    resp = api_client.get("/api/v1/system/worker-status/")
    assert resp.status_code == 200
    assert resp.data["alive"] is True
    assert resp.data["last_heartbeat_at"]  # truthy ISO string
    assert resp.data["metadata"] == {"pid": 4242}


@pytest.mark.django_db
def test_worker_status_reports_dead_when_key_absent(api_client):  # type: ignore[no-untyped-def]
    # No heartbeat posted yet — cache key is absent.
    resp = api_client.get("/api/v1/system/worker-status/")
    assert resp.status_code == 200
    assert resp.data == {"alive": False, "last_heartbeat_at": None, "metadata": {}}


@pytest.mark.django_db
def test_worker_status_requires_auth():  # type: ignore[no-untyped-def]
    resp = APIClient().get("/api/v1/system/worker-status/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_worker_status_handles_corrupt_payload(api_client):  # type: ignore[no-untyped-def]
    """If someone stuffs garbage into the key the endpoint degrades to 'dead'."""
    cache.set(WORKER_HEARTBEAT_KEY, "not-a-dict", timeout=60)
    resp = api_client.get("/api/v1/system/worker-status/")
    assert resp.status_code == 200
    assert resp.data["alive"] is False
