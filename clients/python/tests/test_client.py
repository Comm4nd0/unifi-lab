"""UVLClient tests using httpx MockTransport — no live backend needed."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from uvl_client import UVLAuthError, UVLClient, UVLError, UVLTimeout


def make_transport(
    routes: dict[tuple[str, str], Any],
) -> httpx.MockTransport:
    """routes map (METHOD, path) -> response spec.

    Each spec can be:
    - tuple(status, json_body)
    - tuple(status, json_body, headers_dict)
    - callable(request) -> httpx.Response for fully custom handling
    """

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        spec = routes.get(key)
        if spec is None:
            return httpx.Response(404, json={"detail": f"no mock for {key}"}, request=request)
        if callable(spec):
            return spec(request)
        if len(spec) == 2:
            status, body = spec
            headers = None
        else:
            status, body, headers = spec
        return httpx.Response(status, json=body, headers=headers or {}, request=request)

    return httpx.MockTransport(handler)


async def _patched_client(transport: httpx.MockTransport, **kwargs: Any) -> UVLClient:
    client = UVLClient("https://uvl.test", verify_tls=False, **kwargs)
    await client.__aenter__()
    assert client._http is not None
    await client._http.aclose()
    client._http = httpx.AsyncClient(transport=transport, base_url="https://uvl.test")
    return client


@pytest.mark.asyncio
async def test_login_exchanges_credentials_for_tokens():
    transport = make_transport(
        {
            ("POST", "/api/v1/auth/jwt/create/"): (
                200,
                {"access": "acc-1", "refresh": "ref-1"},
            ),
        }
    )
    client = UVLClient("https://uvl.test", email="a@b.com", password="x", verify_tls=False)
    client._http = httpx.AsyncClient(transport=transport, base_url="https://uvl.test")
    try:
        await client._login()
        assert client._access_token == "acc-1"
        assert client._refresh_token == "ref-1"
    finally:
        await client._http.aclose()


@pytest.mark.asyncio
async def test_401_triggers_refresh_and_retries():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v1/auth/jwt/refresh/":
            return httpx.Response(200, json={"access": "acc-2"}, request=request)
        if request.url.path == "/api/v1/fleets/":
            # First call returns 401, second (after refresh) returns 200.
            if calls.count("GET /api/v1/fleets/") == 1:
                return httpx.Response(401, json={"detail": "expired"}, request=request)
            return httpx.Response(
                200, json={"count": 0, "next": None, "previous": None, "results": []}, request=request
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    client = await _patched_client(transport, access_token="acc-1", refresh_token="ref-1")
    try:
        out = await client.fleets.list()
        assert out == {"count": 0, "next": None, "previous": None, "results": []}
        assert calls == [
            "GET /api/v1/fleets/",
            "POST /api/v1/auth/jwt/refresh/",
            "GET /api/v1/fleets/",
        ]
        assert client._access_token == "acc-2"
    finally:
        if client._http is not None:
            await client._http.aclose()


@pytest.mark.asyncio
async def test_401_without_refresh_raises_auth_error():
    transport = make_transport(
        {("GET", "/api/v1/fleets/"): (401, {"detail": "invalid token"})}
    )
    client = await _patched_client(transport, access_token="acc-1")
    try:
        with pytest.raises(UVLAuthError):
            await client.fleets.list()
    finally:
        if client._http is not None:
            await client._http.aclose()


@pytest.mark.asyncio
async def test_non_2xx_raises_uvlerror_with_status():
    transport = make_transport(
        {("POST", "/api/v1/fleets/"): (400, {"detail": "bad"})}
    )
    client = await _patched_client(transport, access_token="acc-1")
    try:
        with pytest.raises(UVLError) as exc:
            await client.fleets.create(
                name="x",
                controller_target_id="c-1",
                model_code="USW24P250",
                device_count=1,
            )
        assert exc.value.status == 400
    finally:
        if client._http is not None:
            await client._http.aclose()


@pytest.mark.asyncio
async def test_fleets_create_blueprint_path_posts_blueprint_field():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            201, json={"id": "f-1", "state": "ramping"}, request=request
        )

    client = await _patched_client(httpx.MockTransport(handler), access_token="acc-1")
    try:
        await client.fleets.create(
            name="bp-fleet",
            controller_target_id="c-1",
            blueprint_id="bp-1",
        )
    finally:
        if client._http is not None:
            await client._http.aclose()

    assert captured["body"] == {
        "name": "bp-fleet",
        "controller_target": "c-1",
        "auto_adopt": False,
        "blueprint": "bp-1",
    }


@pytest.mark.asyncio
async def test_fleets_create_simple_path_rejects_missing_count():
    client = UVLClient("https://uvl.test", access_token="acc-1", verify_tls=False)
    with pytest.raises(ValueError):
        await client.fleets.create(
            name="x",
            controller_target_id="c-1",
            model_code="USW24P250",
        )


@pytest.mark.asyncio
async def test_wait_for_state_polls_until_target(monkeypatch):  # type: ignore[no-untyped-def]
    states = iter(["creating", "ramping", "active"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "f-1", "state": next(states)},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = await _patched_client(transport, access_token="acc-1")

    # Skip real sleeps during polling.
    import asyncio as _asyncio

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(_asyncio, "sleep", _no_sleep)

    try:
        out = await client.fleets.wait_for_state(
            "f-1", "active", timeout=10, poll_interval=0
        )
        assert out["state"] == "active"
    finally:
        if client._http is not None:
            await client._http.aclose()


@pytest.mark.asyncio
async def test_wait_for_state_times_out(monkeypatch):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "f-1", "state": "creating"}, request=request
        )

    transport = httpx.MockTransport(handler)
    client = await _patched_client(transport, access_token="acc-1")

    # Deterministic clock — jumps past the timeout on the second call.
    clock = {"now": 0.0}

    def fake_monotonic() -> float:
        current = clock["now"]
        clock["now"] += 2.0  # each call advances well past the 1.0s budget
        return current

    monkeypatch.setattr("uvl_client.client.time.monotonic", fake_monotonic)

    import asyncio as _asyncio

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(_asyncio, "sleep", _no_sleep)

    try:
        with pytest.raises(UVLTimeout):
            await client.fleets.wait_for_state(
                "f-1", "active", timeout=1.0, poll_interval=0
            )
    finally:
        if client._http is not None:
            await client._http.aclose()


@pytest.mark.asyncio
async def test_requires_email_or_token_at_construction():
    with pytest.raises(ValueError):
        UVLClient("https://uvl.test")


@pytest.mark.asyncio
async def test_health_endpoint_does_not_require_auth():
    transport = make_transport(
        {("GET", "/api/v1/system/health/"): (200, {"status": "ok", "db": "ok", "redis": "skipped", "version": "0.1.0"})}
    )
    client = UVLClient("https://uvl.test", access_token="acc-1", verify_tls=False)
    client._http = httpx.AsyncClient(transport=transport, base_url="https://uvl.test")
    try:
        result = await client.health()
        assert result["status"] == "ok"
    finally:
        await client._http.aclose()
