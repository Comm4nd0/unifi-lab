"""UosServerClient — verified against a mocked httpx transport.

No network I/O here; ``httpx.MockTransport`` lets us assert the client
hits the right paths with the right payloads for both UniFi OS Server
and legacy Network controllers.
"""

from __future__ import annotations

import json

import httpx
import pytest

from engine.clients.unifi import KIND_LEGACY, KIND_UOS_SERVER, UnifiApiError, UosServerClient


def _make_transport(
    responses: dict[tuple[str, str], tuple[int, dict, dict[str, str] | None]],
) -> httpx.MockTransport:
    """``responses`` keyed on (method, path) returning (status, body, headers)."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in responses:
            return httpx.Response(404, json={"err": f"no mock for {key}"}, request=request)
        status, body, headers = responses[key]
        return httpx.Response(status, json=body, headers=headers or {}, request=request)

    return httpx.MockTransport(handler)


async def _client_with(transport: httpx.MockTransport, **kwargs):  # type: ignore[no-untyped-def]
    client = UosServerClient(
        base_url="https://ctrl.local",
        username="admin",
        password="pw",
        verify_tls=False,
        **kwargs,
    )
    await client.__aenter__()
    # Swap the real transport with our mock, preserving the base URL.
    assert client._client is not None  # pragma: no cover
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=transport, base_url="https://ctrl.local")
    return client


@pytest.mark.asyncio
async def test_uos_server_login_sets_csrf_token():
    transport = _make_transport(
        {
            ("POST", "/api/auth/login"): (
                200,
                {"meta": {"rc": "ok"}},
                {"X-CSRF-Token": "csrf-abc"},
            ),
        }
    )
    client = await _client_with(transport)
    try:
        await client.login()
        assert client._csrf == "csrf-abc"
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_legacy_network_login_uses_different_path():
    transport = _make_transport(
        {
            ("POST", "/api/login"): (200, {"meta": {"rc": "ok"}}, None),
        }
    )
    client = await _client_with(transport, kind=KIND_LEGACY)
    try:
        await client.login()
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_sysinfo_uses_proxy_prefix_on_uos_server():
    transport = _make_transport(
        {
            ("GET", "/proxy/network/api/s/default/stat/sysinfo"): (
                200,
                {"data": [{"version": "8.3.42"}]},
                None,
            ),
        }
    )
    client = await _client_with(transport, kind=KIND_UOS_SERVER)
    try:
        body = await client.sysinfo()
        assert body["data"][0]["version"] == "8.3.42"
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_list_devices_returns_data_array():
    transport = _make_transport(
        {
            ("GET", "/proxy/network/api/s/default/stat/device"): (
                200,
                {"data": [{"mac": "aa:bb:cc:dd:ee:ff", "state": 1}]},
                None,
            ),
        }
    )
    client = await _client_with(transport)
    try:
        devices = await client.list_devices()
        assert len(devices) == 1
        assert devices[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_adopt_posts_devmgr_with_lowercased_mac():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"meta": {"rc": "ok"}}, request=request)

    transport = httpx.MockTransport(handler)
    client = await _client_with(transport)
    try:
        await client.adopt("AA:BB:CC:DD:EE:FF")
        assert captured["path"] == "/proxy/network/api/s/default/cmd/devmgr"
        assert captured["body"] == {"cmd": "adopt", "mac": "aa:bb:cc:dd:ee:ff"}
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_forget_posts_delete_device():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"meta": {"rc": "ok"}}, request=request)

    transport = httpx.MockTransport(handler)
    client = await _client_with(transport)
    try:
        await client.forget("aa:bb:cc:dd:ee:ff")
        assert captured["body"] == {"cmd": "delete-device", "mac": "aa:bb:cc:dd:ee:ff"}
    finally:
        if client._client is not None:
            await client._client.aclose()


@pytest.mark.asyncio
async def test_non_2xx_raises_unifiapierror():
    transport = _make_transport(
        {("POST", "/api/auth/login"): (401, {"meta": {"rc": "error"}}, None)}
    )
    client = await _client_with(transport)
    try:
        with pytest.raises(UnifiApiError) as excinfo:
            await client.login()
        assert excinfo.value.status == 401
    finally:
        if client._client is not None:
            await client._client.aclose()
