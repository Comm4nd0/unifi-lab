"""UniFi OS Server / Legacy Network HTTP client.

Pure httpx async client — deliberately free of Django imports so the
engine process can use it without pulling Django in. The Django side
(e.g. the ``controllers`` app) can import this too for on-demand probes.

Coverage (Phase 1 scope):
- ``login`` — exchanges admin credentials for a session cookie + X-CSRF-Token.
- ``sysinfo`` — controller uptime, version, site count; used as a liveness probe.
- ``list_devices`` — all adopted/pending devices on a site.
- ``adopt`` — POST cmd=adopt against devmgr.
- ``forget`` — POST cmd=delete-device against devmgr.

UniFi OS Server prefixes everything with ``/proxy/network``; legacy Network
servers don't. Pass ``kind`` at construction to pick the right prefix.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

log = logging.getLogger("uvl.engine.clients.unifi")

KIND_UOS_SERVER = "uos-server"
KIND_LEGACY = "legacy-network"


class UnifiApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class UosServerClient:
    """Thin async wrapper over a UniFi controller's REST surface.

    Not intended for high-throughput — opens a connection per call. Callers
    who need many requests in a row should reuse a single client instance
    via ``async with`` so cookies persist.
    """

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        kind: str = KIND_UOS_SERVER,
        site: str = "default",
        verify_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.kind = kind
        self.site = site
        self.verify_tls = verify_tls
        self._client: httpx.AsyncClient | None = None
        self._csrf: str | None = None
        self._timeout = timeout

    # ── lifecycle ────────────────────────────────────────────────────

    async def __aenter__(self) -> UosServerClient:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify_tls,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _site_prefix(self) -> str:
        proxied = "/proxy/network" if self.kind == KIND_UOS_SERVER else ""
        return f"{proxied}/api/s/{self.site}"

    def _auth_path(self) -> str:
        return "/api/auth/login" if self.kind == KIND_UOS_SERVER else "/api/login"

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._csrf:
            h["X-CSRF-Token"] = self._csrf
        return h

    # ── auth ─────────────────────────────────────────────────────────

    async def login(self) -> None:
        assert self._client is not None, "Use as async context manager"
        resp = await self._client.post(
            self._auth_path(),
            json={"username": self.username, "password": self.password, "rememberMe": False},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            raise UnifiApiError(resp.status_code, f"login failed: {resp.text[:200]}")
        # UOS sets X-CSRF-Token on successful login; legacy uses only the session cookie.
        self._csrf = resp.headers.get("X-CSRF-Token")
        log.info("unifi.login.ok", extra={"base": self.base_url, "kind": self.kind})

    # ── reads ────────────────────────────────────────────────────────

    async def sysinfo(self) -> dict[str, Any]:
        return await self._get(f"{self._site_prefix()}/stat/sysinfo")

    async def list_devices(self) -> list[dict[str, Any]]:
        body = await self._get(f"{self._site_prefix()}/stat/device")
        data = body.get("data") if isinstance(body, dict) else body
        return list(data or [])

    # ── writes ───────────────────────────────────────────────────────

    async def adopt(self, mac: str) -> dict[str, Any]:
        return await self._cmd_devmgr({"cmd": "adopt", "mac": mac.lower()})

    async def forget(self, mac: str) -> dict[str, Any]:
        return await self._cmd_devmgr({"cmd": "delete-device", "mac": mac.lower()})

    # ── internals ────────────────────────────────────────────────────

    async def _cmd_devmgr(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post(f"{self._site_prefix()}/cmd/devmgr", payload)

    async def _get(self, path: str) -> Any:
        assert self._client is not None
        resp = await self._client.get(urljoin("/", path), headers=self._headers())
        return self._check(resp)

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        assert self._client is not None
        resp = await self._client.post(urljoin("/", path), json=body, headers=self._headers())
        return self._check(resp)

    def _check(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            raise UnifiApiError(resp.status_code, resp.text[:300])
        if not resp.content:
            return None
        return resp.json()
