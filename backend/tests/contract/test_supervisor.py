"""Supervisor task lifecycle — idempotent spawn, clean despawn."""

from __future__ import annotations

import asyncio

import pytest

from engine.config import EngineConfig
from engine.supervisor import Supervisor


def _cfg() -> EngineConfig:
    # Values don't matter — the tests never hit Redis or the DB.
    return EngineConfig(
        database_url="postgresql://x:x@localhost/x",
        redis_url="redis://localhost/0",
        channels_layer_url="redis://localhost/2",
        django_api_base="http://localhost:8003",
        worker_token="",
        log_level="INFO",
    )


@pytest.mark.asyncio
async def test_spawn_is_idempotent():
    sup = Supervisor(_cfg())
    await sup._spawn_device("a")
    await sup._spawn_device("a")
    assert len(sup._tasks) == 1
    await sup.shutdown()


@pytest.mark.asyncio
async def test_spawn_starts_a_running_task():
    sup = Supervisor(_cfg())
    await sup._spawn_device("a")
    task = sup._tasks["a"]
    assert not task.done()
    # Let it run one tick, then shut down.
    await asyncio.sleep(0)
    await sup.shutdown()
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_despawn_removes_the_task():
    sup = Supervisor(_cfg())
    await sup._spawn_device("a")
    await sup._despawn_device("a")
    assert "a" not in sup._tasks
    await sup.shutdown()
