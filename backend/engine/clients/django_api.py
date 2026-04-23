"""Typed HTTP client from the worker to the Django service.

Calls are authenticated via a shared bearer token (``UVL_WORKER_TOKEN``)
that Django validates with the ``IsWorkerRequest`` permission. This is
not the user-facing JWT system — it's a narrow worker channel for
state-change callbacks like ``mark-adopted``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class DjangoApiClient:
    base_url: str
    token: str = ""
    verify_tls: bool = True
    timeout: float = 10.0

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_device(self, device_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/devices/{device_id}/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def create_device(self, *, model_code: str, controller_target_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/devices/",
                json={"model_code": model_code, "controller_target": controller_target_id},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def mark_device_adopted(self, device_id: str) -> dict[str, Any]:
        """Worker callback — confirms a device has been adopted controller-side."""
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/devices/{device_id}/mark-adopted/",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={},
            )
            resp.raise_for_status()
            return resp.json()
