"""WebSocket consumer — live inform-exchange stream for a single device.

URL: ``/ws/devices/<device_id>/inform?token=<access_jwt>&since_seq=<n>``

Protocol (matches ``schemas/ws_envelope.v1.json``):
- On connect: send ``{type: "connection.ready", seq: <last>, ...}``.
- Then replay recent exchanges (capped) as ``{type: "inform.exchange", seq, data}``.
- Subsequently, publishes from the engine arrive via the channel group
  ``device:<id>`` and are forwarded with monotonic ``seq`` numbers.

JWT is carried on the querystring because browsers can't set headers on a
WebSocket upgrade. The token is validated with SimpleJWT; on failure we
close 4401.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

log = logging.getLogger("uvl.ws.devices")

SNAPSHOT_SIZE = 50


def _envelope(type_: str, data: dict[str, Any], *, seq: int | None = None) -> dict[str, Any]:
    env: dict[str, Any] = {
        "v": 1,
        "type": type_,
        "ts": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }
    if seq is not None:
        env["seq"] = seq
    return env


@database_sync_to_async
def _authenticate(token: str):  # type: ignore[no-untyped-def]
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(token)
        user = auth.get_user(validated)
    except (InvalidToken, TokenError):
        return None
    return user


@database_sync_to_async
def _snapshot(device_id: str, since_seq: int) -> list[dict[str, Any]]:
    from apps.devices.models import InformExchange, VirtualDevice

    if not VirtualDevice.objects.filter(pk=device_id).exists():
        return []
    qs = (
        InformExchange.objects.filter(device_id=device_id)
        .order_by("-exchanged_at")
        .values("id", "exchange_type", "payload_in", "payload_out", "exchanged_at")[:SNAPSHOT_SIZE]
    )
    # Reverse so client receives in chronological order.
    rows = list(qs)[::-1]
    # If the client is resuming at since_seq, drop anything <= that.
    return [
        {
            "id": str(r["id"]),
            "exchange_type": r["exchange_type"],
            "payload_in": r["payload_in"],
            "payload_out": r["payload_out"],
            "exchanged_at": r["exchanged_at"].isoformat() if r["exchanged_at"] else None,
        }
        for r in rows
    ][since_seq:]


class DeviceInformConsumer(AsyncJsonWebsocketConsumer):
    def _group_name(self) -> str:
        # Channels group names only permit [a-zA-Z0-9._-]; use dot, not colon.
        return f"device.{self.device_id}"

    async def connect(self) -> None:
        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [""])[0]
        try:
            since_seq = int((qs.get("since_seq") or ["0"])[0])
        except ValueError:
            since_seq = 0

        user = await _authenticate(token) if token else None
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        self.seq = 0
        await self.channel_layer.group_add(self._group_name(), self.channel_name)
        await self.accept()

        await self.send_json(
            _envelope("connection.ready", {"device_id": self.device_id}, seq=self.seq),
        )

        snapshot = await _snapshot(self.device_id, since_seq)
        for row in snapshot:
            self.seq += 1
            await self.send_json(_envelope("inform.exchange", row, seq=self.seq))

    async def disconnect(self, code: int) -> None:
        group = self._group_name()
        if getattr(self, "channel_name", None):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def device_event(self, event: dict[str, Any]) -> None:
        """Handler for group messages sent with ``type='device.event'``."""
        self.seq += 1
        payload = event.get("payload", {})
        await self.send_json(
            _envelope(
                payload.get("type", "inform.exchange"), payload.get("data", {}), seq=self.seq
            ),
        )
