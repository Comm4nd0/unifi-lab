"""UVLClient — async HTTP client with JWT auth and ergonomic sub-clients.

Design:
- One ``httpx.AsyncClient`` per ``UVLClient`` instance, opened in
  ``__aenter__`` and closed in ``__aexit__``.
- Auth: either (email, password) — exchanges for a JWT pair — or a
  pre-obtained ``access_token``. 401 responses trigger a one-shot refresh
  when a refresh token is available.
- Sub-clients (``uvl.fleets``, ``uvl.devices`` …) are thin wrappers over
  the HTTP layer with domain-specific helpers.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .exceptions import UVLAuthError, UVLError, UVLTimeout
from .types import Blueprint, ControllerTarget, Fleet, Paginated, VirtualDevice


def _raise_for_response(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    body: Any
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    if resp.status_code in (401, 403):
        raise UVLAuthError(
            _format_message(body, resp.status_code), status=resp.status_code, body=body
        )
    raise UVLError(_format_message(body, resp.status_code), status=resp.status_code, body=body)


def _format_message(body: Any, status: int) -> str:
    if isinstance(body, dict) and "detail" in body:
        return f"{status}: {body['detail']}"
    if isinstance(body, str) and body:
        return f"{status}: {body[:200]}"
    return f"{status}"


class UVLClient:
    def __init__(
        self,
        base_url: str,
        *,
        email: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        verify_tls: bool = True,
        timeout: float = 30.0,
    ) -> None:
        if not any([email, access_token]):
            raise ValueError("Either email+password or access_token is required")
        self.base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._verify_tls = verify_tls
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None

        self.fleets = _FleetsClient(self)
        self.devices = _DevicesClient(self)
        self.blueprints = _BlueprintsClient(self)
        self.controllers = _ControllersClient(self)
        self.firmware = _FirmwareClient(self)
        self.system = _SystemClient(self)

    # ── lifecycle ─────────────────────────────────────────────────────

    async def __aenter__(self) -> "UVLClient":
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            verify=self._verify_tls,
            timeout=self._timeout,
        )
        if self._access_token is None:
            await self._login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ── auth ──────────────────────────────────────────────────────────

    async def _login(self) -> None:
        assert self._http is not None, "Use UVLClient as async context manager"
        if not (self._email and self._password):
            raise UVLAuthError("Login required but email/password missing")
        resp = await self._http.post(
            "/api/v1/auth/jwt/create/",
            json={"email": self._email, "password": self._password},
        )
        if not resp.is_success:
            _raise_for_response(resp)
        data = resp.json()
        self._access_token = data["access"]
        self._refresh_token = data.get("refresh")

    async def _try_refresh(self) -> bool:
        if not (self._http and self._refresh_token):
            return False
        resp = await self._http.post(
            "/api/v1/auth/jwt/refresh/",
            json={"refresh": self._refresh_token},
        )
        if not resp.is_success:
            return False
        data = resp.json()
        self._access_token = data["access"]
        if "refresh" in data:
            self._refresh_token = data["refresh"]
        return True

    # ── request plumbing ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            raise UVLAuthError("Not authenticated — enter the async context first")
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        assert self._http is not None
        headers = self._headers()
        resp = await self._http.request(
            method, path, headers=headers, json=json, params=params, files=files
        )
        if resp.status_code == 401 and await self._try_refresh():
            headers = self._headers()
            resp = await self._http.request(
                method, path, headers=headers, json=json, params=params, files=files
            )
        _raise_for_response(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ── convenience ───────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Liveness probe — no auth required."""
        assert self._http is not None
        resp = await self._http.get("/api/v1/system/health/")
        _raise_for_response(resp)
        return resp.json()

    # Generic wait-for helper — sub-clients reuse this.
    async def _wait_until(
        self,
        fetch: Callable[[], Awaitable[dict[str, Any]]],
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float,
        poll_interval: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = await fetch()
            if predicate(last):
                return last
            await asyncio.sleep(poll_interval)
        raise UVLTimeout(
            f"wait_until exceeded {timeout}s (last observed state: {last.get('state')!r})"
        )


# ── Sub-clients ──────────────────────────────────────────────────────


class _SubClient:
    def __init__(self, parent: UVLClient) -> None:
        self._client = parent


class _SystemClient(_SubClient):
    async def health(self) -> dict[str, Any]:
        return await self._client.health()

    async def version(self) -> dict[str, Any]:
        return await self._client._request("GET", "/api/v1/system/version/")


class _ControllersClient(_SubClient):
    async def list(self) -> Paginated[ControllerTarget]:
        return await self._client._request("GET", "/api/v1/controllers/")

    async def get(self, controller_id: str) -> ControllerTarget:
        return await self._client._request("GET", f"/api/v1/controllers/{controller_id}/")

    async def create(self, **fields: Any) -> ControllerTarget:
        return await self._client._request("POST", "/api/v1/controllers/", json=fields)

    async def delete(self, controller_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/controllers/{controller_id}/")

    async def health_check(self, controller_id: str) -> ControllerTarget:
        return await self._client._request(
            "POST", f"/api/v1/controllers/{controller_id}/health-check/"
        )


class _BlueprintsClient(_SubClient):
    async def list(self) -> Paginated[Blueprint]:
        return await self._client._request("GET", "/api/v1/blueprints/")

    async def get(self, blueprint_id: str) -> Blueprint:
        return await self._client._request("GET", f"/api/v1/blueprints/{blueprint_id}/")

    async def create(self, *, name: str, source_yaml: str) -> Blueprint:
        return await self._client._request(
            "POST",
            "/api/v1/blueprints/",
            json={"name": name, "source_yaml": source_yaml},
        )

    async def update(self, blueprint_id: str, *, name: str, source_yaml: str) -> Blueprint:
        return await self._client._request(
            "PUT",
            f"/api/v1/blueprints/{blueprint_id}/",
            json={"name": name, "source_yaml": source_yaml},
        )

    async def delete(self, blueprint_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/blueprints/{blueprint_id}/")

    async def validate(self, source_yaml: str) -> dict[str, Any]:
        return await self._client._request(
            "POST",
            "/api/v1/blueprints/validate/",
            json={"source_yaml": source_yaml},
        )


class _DevicesClient(_SubClient):
    async def list(self, *, fleet_id: str | None = None) -> Paginated[VirtualDevice]:
        params = {"fleet": fleet_id} if fleet_id else None
        return await self._client._request("GET", "/api/v1/devices/", params=params)

    async def get(self, device_id: str) -> VirtualDevice:
        return await self._client._request("GET", f"/api/v1/devices/{device_id}/")

    async def create(
        self,
        *,
        model_code: str,
        controller_target_id: str | None = None,
        fleet_id: str | None = None,
        firmware_version: str = "",
    ) -> VirtualDevice:
        body: dict[str, Any] = {"model_code": model_code, "firmware_version": firmware_version}
        if controller_target_id:
            body["controller_target"] = controller_target_id
        if fleet_id:
            body["fleet"] = fleet_id
        return await self._client._request("POST", "/api/v1/devices/", json=body)

    async def delete(self, device_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/devices/{device_id}/")

    async def force_inform(self, device_id: str) -> dict[str, Any]:
        return await self._client._request("POST", f"/api/v1/devices/{device_id}/force-inform/")

    async def inform_log(self, device_id: str) -> Paginated[dict[str, Any]]:
        return await self._client._request("GET", f"/api/v1/devices/{device_id}/inform-log/")


class _FleetsClient(_SubClient):
    async def list(self) -> Paginated[Fleet]:
        return await self._client._request("GET", "/api/v1/fleets/")

    async def get(self, fleet_id: str) -> Fleet:
        return await self._client._request("GET", f"/api/v1/fleets/{fleet_id}/")

    async def create(
        self,
        *,
        name: str,
        controller_target_id: str,
        blueprint_id: str | None = None,
        model_code: str | None = None,
        device_count: int | None = None,
        auto_adopt: bool = False,
    ) -> Fleet:
        body: dict[str, Any] = {
            "name": name,
            "controller_target": controller_target_id,
            "auto_adopt": auto_adopt,
        }
        if blueprint_id:
            body["blueprint"] = blueprint_id
        else:
            if not (model_code and device_count):
                raise ValueError(
                    "Either blueprint_id or both model_code+device_count must be provided"
                )
            body["model_code"] = model_code
            body["device_count"] = device_count
        return await self._client._request("POST", "/api/v1/fleets/", json=body)

    async def pause(self, fleet_id: str) -> Fleet:
        return await self._client._request("POST", f"/api/v1/fleets/{fleet_id}/pause/")

    async def resume(self, fleet_id: str) -> Fleet:
        return await self._client._request("POST", f"/api/v1/fleets/{fleet_id}/resume/")

    async def teardown(self, fleet_id: str) -> Fleet:
        return await self._client._request("POST", f"/api/v1/fleets/{fleet_id}/teardown/")

    async def delete(self, fleet_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/fleets/{fleet_id}/")

    async def wait_for_state(
        self,
        fleet_id: str,
        target: str,
        *,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ) -> Fleet:
        """Block until the fleet's ``state`` matches ``target`` or timeout."""

        async def fetch() -> dict[str, Any]:
            return await self.get(fleet_id)

        return await self._client._wait_until(
            fetch,
            lambda f: f.get("state") == target,
            timeout=timeout,
            poll_interval=poll_interval,
        )


class _FirmwareClient(_SubClient):
    async def list(self) -> Paginated[dict[str, Any]]:
        return await self._client._request("GET", "/api/v1/firmware/")

    async def upload(self, path: str, *, filename: str | None = None) -> dict[str, Any]:
        import os

        name = filename or os.path.basename(path)
        with open(path, "rb") as f:
            files = {"file": (name, f, "application/octet-stream")}
            return await self._client._request("POST", "/api/v1/firmware/", files=files)

    async def delete(self, blob_id: str) -> None:
        await self._client._request("DELETE", f"/api/v1/firmware/{blob_id}/")
