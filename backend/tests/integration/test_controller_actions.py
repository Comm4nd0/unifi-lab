"""Controller target action endpoints: health-check, rotate secrets."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from engine.clients.unifi import UnifiApiError


@pytest.mark.django_db
def test_health_check_runs_probe(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    body = resp.data
    # Probe against 127.0.0.1:443 in the test env will usually fail; accept any
    # of the deterministic outcomes.
    assert body["health"] in {"ok", "auth-failed", "unreachable", "unknown"}
    assert body["last_verified_at"] is not None
    # Steps array is always present with the three fixed stages.
    assert [s["name"] for s in body["steps"]] == ["parse_url", "tcp_connect", "api_login"]
    for step in body["steps"]:
        assert step["status"] in {"ok", "failed", "skipped"}
        assert "label" in step


# The API-login stage of the probe is tested by mocking UosServerClient so
# the suite doesn't touch the network. The TCP stage is mocked to always
# succeed so the login result is what determines the health.


@pytest.fixture
def _mock_tcp_ok(monkeypatch):  # type: ignore[no-untyped-def]
    """Monkeypatch socket.create_connection so the TCP step always succeeds."""
    import contextlib

    @contextlib.contextmanager
    def fake_conn(*_a, **_kw):  # type: ignore[no-untyped-def]
        yield object()

    monkeypatch.setattr("apps.controllers.views.socket.create_connection", fake_conn)
    return monkeypatch


def _client_that_logs_in(raises: Exception | None = None):  # type: ignore[no-untyped-def]
    """Factory returning a stub ``UosServerClient`` context manager."""

    class _Stub:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def login(self) -> None:
            if raises is not None:
                raise raises

    def factory(**_kwargs):  # type: ignore[no-untyped-def]
        return _Stub()

    return factory


@pytest.mark.django_db
def test_health_check_ok_when_login_succeeds(api_client, controller_target, _mock_tcp_ok):  # type: ignore[no-untyped-def]
    with patch("apps.controllers.views.UosServerClient", _client_that_logs_in()):
        resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    assert resp.data["health"] == "ok"


@pytest.mark.django_db
def test_health_check_auth_failed_on_4xx(api_client, controller_target, _mock_tcp_ok):  # type: ignore[no-untyped-def]
    with patch(
        "apps.controllers.views.UosServerClient",
        _client_that_logs_in(raises=UnifiApiError(401, "bad creds")),
    ):
        resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    assert resp.data["health"] == "auth-failed"


@pytest.mark.django_db
def test_health_check_unreachable_on_5xx(api_client, controller_target, _mock_tcp_ok):  # type: ignore[no-untyped-def]
    with patch(
        "apps.controllers.views.UosServerClient",
        _client_that_logs_in(raises=UnifiApiError(502, "gateway down")),
    ):
        resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    assert resp.data["health"] == "unreachable"


@pytest.mark.django_db
def test_health_check_unreachable_on_network_error(api_client, controller_target, _mock_tcp_ok):  # type: ignore[no-untyped-def]
    with patch(
        "apps.controllers.views.UosServerClient",
        _client_that_logs_in(raises=ConnectionError("boom")),
    ):
        resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    assert resp.data["health"] == "unreachable"


@pytest.mark.django_db
def test_health_check_unreachable_when_tcp_fails(api_client, controller_target, monkeypatch):  # type: ignore[no-untyped-def]
    """TCP short-circuit — login path shouldn't even be attempted."""

    def raise_conn(*_a, **_kw):  # type: ignore[no-untyped-def]
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr("apps.controllers.views.socket.create_connection", raise_conn)
    with patch("apps.controllers.views.UosServerClient") as mocked_client:
        resp = api_client.post(f"/api/v1/controllers/{controller_target.id}/health-check/")
    assert resp.status_code == 200
    assert resp.data["health"] == "unreachable"
    assert not mocked_client.called  # login never attempted
    # TCP step failed, API step marked skipped.
    steps = {s["name"]: s for s in resp.data["steps"]}
    assert steps["tcp_connect"]["status"] == "failed"
    assert steps["api_login"]["status"] == "skipped"
    _ = AsyncMock  # keep the import warm for future expansion


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
