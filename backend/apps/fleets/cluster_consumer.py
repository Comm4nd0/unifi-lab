"""WebSocket consumer for cluster-wide events.

URL: ``/ws/cluster/?token=<access_jwt>``

Subscribes to the shared ``cluster`` channel group, which receives a
copy of every ``publish_fleet_event`` fan-out. The dashboard uses this
to invalidate ``fleets``/``devices``/``flow stats`` queries the moment
a relevant event hits, so it feels live without polling on a tight
interval.

Auth: same JWT querystring flow as ``FleetConsumer``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .events import CLUSTER_GROUP

log = logging.getLogger("uvl.ws.cluster")


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


def _envelope(type_: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": type_,
        "ts": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


class ClusterConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [""])[0]
        user = await _authenticate(token) if token else None
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        await self.channel_layer.group_add(CLUSTER_GROUP, self.channel_name)
        await self.accept()
        await self.send_json(_envelope("cluster.ready", {}))

    async def disconnect(self, code: int) -> None:
        if getattr(self, "channel_name", None):
            await self.channel_layer.group_discard(CLUSTER_GROUP, self.channel_name)

    async def fleet_event(self, event: dict[str, Any]) -> None:
        """Forward every fleet event published to the cluster group."""
        payload = event.get("payload") or {}
        await self.send_json(payload)

    async def notification_event(self, event: dict[str, Any]) -> None:
        """Forward notification events to connected clients."""
        payload = event.get("payload") or {}
        await self.send_json(payload)
