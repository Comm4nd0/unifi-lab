"""WebSocket consumer for fleet lifecycle events.

URL: ``/ws/fleets/<fleet_id>/?token=<access_jwt>``

Auth: shared JWT flow with the rest of the API — client passes the access
token on the querystring (browsers can't set headers on WebSocket
upgrade). On failure we close 4401.

On connect the consumer snapshots the current fleet state via Django
ORM and sends a ``fleet.snapshot`` envelope. Subsequent events come
from the channels layer group populated by ``apps.fleets.events``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

log = logging.getLogger("uvl.ws.fleets")


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
def _fleet_snapshot(fleet_id: str) -> dict[str, Any] | None:
    from apps.fleets.models import Fleet

    try:
        fleet = Fleet.objects.get(pk=fleet_id)
    except Fleet.DoesNotExist:
        return None
    counts: dict[str, int] = {}
    for row in fleet.devices.values("state").all():
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {
        "id": str(fleet.id),
        "state": fleet.state,
        "device_count": fleet.device_count,
        "device_states": counts,
    }


def _envelope(type_: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": type_,
        "ts": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


class FleetConsumer(AsyncJsonWebsocketConsumer):
    def _group_name(self) -> str:
        return f"fleet.{self.fleet_id}"

    async def connect(self) -> None:
        self.fleet_id = self.scope["url_route"]["kwargs"]["fleet_id"]
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [""])[0]
        user = await _authenticate(token) if token else None
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        await self.channel_layer.group_add(self._group_name(), self.channel_name)
        await self.accept()

        snapshot = await _fleet_snapshot(self.fleet_id)
        if snapshot is None:
            await self.send_json(_envelope("fleet.not_found", {"fleet_id": self.fleet_id}))
            await self.close(code=4404)
            return

        await self.send_json(_envelope("fleet.snapshot", snapshot))

    async def disconnect(self, code: int) -> None:
        if getattr(self, "channel_name", None):
            await self.channel_layer.group_discard(self._group_name(), self.channel_name)

    async def fleet_event(self, event: dict[str, Any]) -> None:
        """Handler for group_send messages routed to ``type='fleet.event'``."""
        payload = event.get("payload") or {}
        await self.send_json(payload)
