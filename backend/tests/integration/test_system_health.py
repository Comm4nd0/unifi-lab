from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_endpoint_is_public():
    client = APIClient()
    resp = client.get("/api/v1/system/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
