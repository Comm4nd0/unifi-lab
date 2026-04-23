"""Inform session lifecycle — the wire-level conversation with a controller.

Handles TNBU framing, AES encryption, key rotation on adoption, and the
periodic heartbeat POST. Intentionally free of Django imports so the
engine process can load this without pulling in the ORM.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from engine.protocol.codec import decode_inform, encode_inform
from engine.protocol.keys import DEFAULT_INFORM_KEY

log = logging.getLogger("uvl.engine.inform_session")


class InformSession:
    HEARTBEAT_INTERVAL_SECONDS = 10

    def __init__(
        self,
        controller_inform_url: str,
        *,
        mac: bytes,
        model: str,
        serial: str,
        firmware: str,
        verify_tls: bool = True,
        use_gcm: bool = True,
    ) -> None:
        self._url = self._build_url(controller_inform_url)
        self._mac = mac
        self._model = model
        self._serial = serial
        self._firmware = firmware
        self._verify = verify_tls
        self._use_gcm = use_gcm
        self._key: bytes = DEFAULT_INFORM_KEY
        self._using_default = True
        self._cfg_version = "0"
        self._session_start = time.monotonic()

    @staticmethod
    def _build_url(base: str) -> str:
        base = base.rstrip("/")
        return base if base.endswith("/inform") else base + "/inform"

    @property
    def using_default_key(self) -> bool:
        return self._using_default

    # ── payload building ─────────────────────────────────────────────

    def _build_payload(self) -> dict[str, Any]:
        mac_str = ":".join(f"{b:02x}" for b in self._mac)
        return {
            "board_rev": 2,
            "cfgversion": self._cfg_version,
            "default": self._using_default,
            "hostname": f"{self._model.lower()}-{self._serial.lower()}",
            "inform_url": self._url,
            "ip": "0.0.0.0",
            "mac": mac_str,
            "model": self._model,
            "serial": self._serial,
            "uptime": int(time.monotonic() - self._session_start),
            "version": self._firmware,
            "time": int(time.time()),
        }

    # ── wire exchange ────────────────────────────────────────────────

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        frame = encode_inform(
            payload=payload,
            key=self._key,
            mac=self._mac,
            use_gcm=self._use_gcm,
        )
        async with httpx.AsyncClient(verify=self._verify, timeout=15.0) as client:
            resp = await client.post(
                self._url,
                content=frame,
                headers={"Content-Type": "application/x-binary-data"},
            )
            resp.raise_for_status()
        return decode_inform(resp.content, key=self._key)

    def _apply_mgmt_cfg(self, response: dict[str, Any]) -> None:
        mgmt = response.get("mgmt_cfg")
        if not isinstance(mgmt, dict):
            return
        if "key" in mgmt:
            new_key = bytes.fromhex(str(mgmt["key"]))
            if new_key != self._key:
                self._key = new_key
                self._using_default = False
                log.info("inform_session.key_rotated")
        if "cfgversion" in mgmt:
            self._cfg_version = str(mgmt["cfgversion"])
        if "inform_url" in mgmt:
            new_url = str(mgmt["inform_url"])
            if new_url != self._url:
                log.info("inform_session.url_changed  new=%s", new_url)
                self._url = new_url

    # ── public API (called by VirtualDevice) ─────────────────────────

    async def adopt(self) -> dict[str, Any]:
        """Send the initial inform and process any immediate adoption response."""
        payload = self._build_payload()
        response = await self._post(payload)
        self._apply_mgmt_cfg(response)
        rtype = response.get("_type", "noop")
        log.info("inform_session.adopt  type=%s", rtype)
        return response

    async def heartbeat_once(self) -> dict[str, Any]:
        """Send one heartbeat inform and apply any config updates in the response."""
        payload = self._build_payload()
        response = await self._post(payload)
        self._apply_mgmt_cfg(response)
        return response
