"""WebSocket consumer auth + snapshot.

These tests exercise ``channels.testing.WebsocketCommunicator``. The snapshot
test is skipped under SQLite (the in-memory DB doesn't share across the
async + sync threads cleanly). It runs when UVL_DATABASE_URL points at
Postgres.
"""

from __future__ import annotations

import os
import uuid

import pytest
from channels.testing import WebsocketCommunicator

from config.asgi import application


@pytest.mark.asyncio
async def test_connect_without_token_is_rejected() -> None:
    fake_device_id = str(uuid.uuid4())
    communicator = WebsocketCommunicator(application, f"/ws/devices/{fake_device_id}/inform")
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


@pytest.mark.asyncio
async def test_connect_with_bad_token_is_rejected() -> None:
    fake_device_id = str(uuid.uuid4())
    communicator = WebsocketCommunicator(
        application, f"/ws/devices/{fake_device_id}/inform?token=not-a-jwt"
    )
    connected, close_code = await communicator.connect()
    assert connected is False
    assert close_code == 4401


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.skipif(
    "sqlite" in os.environ.get("UVL_DATABASE_URL", "sqlite"),
    reason="Channels + SQLite async tests deadlock; requires Postgres",
)
async def test_connect_with_valid_token_receives_snapshot(admin_user, controller_target):  # type: ignore[no-untyped-def]
    from channels.db import database_sync_to_async
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.devices.services import create_device

    device = await database_sync_to_async(create_device)(
        model_code="USW24P250",
        controller_target_id=str(controller_target.id),
    )
    access = str(RefreshToken.for_user(admin_user).access_token)
    communicator = WebsocketCommunicator(
        application, f"/ws/devices/{device.id}/inform?token={access}"
    )
    connected, _ = await communicator.connect()
    assert connected is True
    first = await communicator.receive_json_from()
    assert first["type"] == "connection.ready"
    assert first["data"]["device_id"] == str(device.id)
    await communicator.disconnect()
