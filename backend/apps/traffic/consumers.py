"""WebSocket consumer for live traffic flow events.

URL: ``/ws/traffic/<fleet_id>/?token=<access_jwt>``

On connect: authenticate, send a snapshot of the last ``SNAPSHOT_LIMIT``
flow records for the fleet, then poll the DB every ``POLL_SECONDS`` for new
rows and push them as ``traffic.flows`` envelopes.

Polling rather than Channels group_send keeps the worker decoupled from
Django/ASGI — the ticker writes to Postgres, the consumer tails it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

log = logging.getLogger("uvl.ws.traffic")

POLL_SECONDS = 5
SNAPSHOT_LIMIT = 30


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _envelope(type_: str, data: Any) -> dict[str, Any]:
    return {
        "v": 1,
        "type": type_,
        "ts": _utcnow().isoformat(),
        "data": data,
    }


@database_sync_to_async
def _authenticate(token: str):  # type: ignore[no-untyped-def]
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

    try:
        auth = JWTAuthentication()
        return auth.get_user(auth.get_validated_token(token))
    except (InvalidToken, TokenError):
        return None


@database_sync_to_async
def _recent_flows(fleet_id: str, *, limit: int) -> list[dict[str, Any]]:
    from apps.traffic.models import FlowRecord
    from apps.traffic.serializers import FlowRecordSerializer

    qs = (
        FlowRecord.objects.filter(device__fleet_id=fleet_id)
        .select_related("device")
        .order_by("-reported_at")[:limit]
    )
    return FlowRecordSerializer(list(reversed(list(qs))), many=True).data  # type: ignore[return-value]


@database_sync_to_async
def _flows_since(fleet_id: str, since: datetime | None) -> tuple[list[dict[str, Any]], datetime]:
    from apps.traffic.models import FlowRecord
    from apps.traffic.serializers import FlowRecordSerializer

    now = _utcnow()
    qs = FlowRecord.objects.filter(device__fleet_id=fleet_id).select_related("device")
    if since is not None:
        qs = qs.filter(reported_at__gt=since)
    qs = qs.order_by("reported_at")[:50]
    rows = FlowRecordSerializer(list(qs), many=True).data  # type: ignore[assignment]
    return rows, now  # type: ignore[return-value]


class TrafficFlowConsumer(AsyncJsonWebsocketConsumer):
    """Streams flow records for a fleet via WebSocket polling."""

    async def connect(self) -> None:
        self.fleet_id: str = self.scope["url_route"]["kwargs"]["fleet_id"]
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [""])[0]
        user = await _authenticate(token) if token else None
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        self._stop = asyncio.Event()
        await self.accept()

        # Snapshot: last N flows
        snapshot = await _recent_flows(self.fleet_id, limit=SNAPSHOT_LIMIT)
        await self.send_json(_envelope("traffic.snapshot", snapshot))

        self._poll_task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, code: int) -> None:
        self._stop.set()
        task = getattr(self, "_poll_task", None)
        if task and not task.done():
            task.cancel()

    async def _poll_loop(self) -> None:
        last_ts: datetime | None = _utcnow()
        while not self._stop.is_set():
            try:
                await asyncio.sleep(POLL_SECONDS)
                if self._stop.is_set():
                    break
                flows, last_ts = await _flows_since(self.fleet_id, last_ts)
                if flows:
                    await self.send_json(_envelope("traffic.flows", flows))
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("traffic.ws.poll_error fleet=%s", self.fleet_id)
