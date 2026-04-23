"""Cluster WebSocket consumer — auth + fan-out."""

from __future__ import annotations

import os

import pytest
from channels.testing import WebsocketCommunicator

from config.asgi import application


@pytest.mark.asyncio
async def test_cluster_rejects_missing_token() -> None:
    communicator = WebsocketCommunicator(application, "/ws/cluster/")
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


@pytest.mark.asyncio
async def test_cluster_rejects_bad_token() -> None:
    communicator = WebsocketCommunicator(application, "/ws/cluster/?token=not-a-jwt")
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.skipif(
    "sqlite" in os.environ.get("UVL_DATABASE_URL", "sqlite"),
    reason="Channels + SQLite async tests deadlock; requires Postgres",
)
async def test_cluster_sends_ready_then_relays_fleet_events(admin_user):  # type: ignore[no-untyped-def]
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.fleets.events import publish_fleet_event

    access = str(RefreshToken.for_user(admin_user).access_token)
    communicator = WebsocketCommunicator(application, f"/ws/cluster/?token={access}")
    connected, _ = await communicator.connect()
    assert connected is True

    first = await communicator.receive_json_from()
    assert first["type"] == "cluster.ready"

    # Publish a synthetic event — it should land on the cluster socket.
    publish_fleet_event("abc-fleet", "fleet.state_changed", state="ramping")
    envelope = await communicator.receive_json_from()
    assert envelope["type"] == "fleet.state_changed"
    assert envelope["data"]["fleet_id"] == "abc-fleet"
    assert envelope["data"]["state"] == "ramping"

    await communicator.disconnect()
