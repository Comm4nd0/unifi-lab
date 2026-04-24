"""WebSocket consumer for firmware ingestion progress.

URL: ``/ws/firmware/<blob_id>/?token=<access_jwt>``

On connect: authenticate JWT, join the ``firmware.<blob_id>`` Channels group,
and emit a ``firmware.snapshot`` with the blob's current state.
Subsequent progress events come from the Celery task via ``group_send``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

log = logging.getLogger("uvl.ws.firmware")


@database_sync_to_async
def _authenticate(token: str):  # type: ignore[no-untyped-def]
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(token)
        return auth.get_user(validated)
    except (InvalidToken, TokenError):
        return None


@database_sync_to_async
def _blob_snapshot(blob_id: str) -> dict[str, Any] | None:
    from apps.firmware.models import FirmwareBlob

    try:
        blob = FirmwareBlob.objects.get(pk=blob_id)
    except FirmwareBlob.DoesNotExist:
        return None
    return {
        "id": str(blob.id),
        "filename": blob.filename,
        "state": blob.state,
        "model_codes": blob.model_codes,
        "version": blob.version,
        "ingest_error": blob.ingest_error,
    }


def _envelope(type_: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": type_,
        "ts": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


class FirmwareProgressConsumer(AsyncJsonWebsocketConsumer):
    def _group_name(self) -> str:
        return f"firmware.{self.blob_id}"

    async def connect(self) -> None:
        self.blob_id: str = self.scope["url_route"]["kwargs"]["blob_id"]
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [""])[0]
        user = await _authenticate(token) if token else None
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        await self.channel_layer.group_add(self._group_name(), self.channel_name)
        await self.accept()

        snapshot = await _blob_snapshot(self.blob_id)
        if snapshot is None:
            await self.send_json(_envelope("firmware.not_found", {"blob_id": self.blob_id}))
            await self.close(code=4404)
            return

        await self.send_json(_envelope("firmware.snapshot", snapshot))

    async def disconnect(self, code: int) -> None:
        if getattr(self, "channel_name", None):
            await self.channel_layer.group_discard(self._group_name(), self.channel_name)

    async def firmware_progress(self, event: dict[str, Any]) -> None:
        """Handler for group_send messages with ``type='firmware.progress'``."""
        payload = event.get("payload") or {}
        await self.send_json(_envelope("firmware.progress", payload))
