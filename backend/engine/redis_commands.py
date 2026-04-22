"""Redis pub/sub subscriber for worker commands.

Complements ``apps.common.worker_commands`` on the Django side.

Usage::

    async for cmd in subscribe_worker_commands(redis_url, channels=[CHANNEL_DEVICES]):
        await handle(cmd)

Commands arrive as JSON envelopes with ``channel`` and ``action`` keys plus
action-specific fields. This module does not know about business logic;
the supervisor decides what to do with each command.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

log = logging.getLogger("uvl.engine.redis_commands")

CHANNEL_DEVICES = "worker:commands:devices"


async def subscribe_worker_commands(
    redis_url: str,
    *,
    channels: list[str],
) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded command envelopes forever. Caller handles cancellation."""
    import redis.asyncio as redis_async

    client = redis_async.from_url(redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(*channels)
    log.info("redis_commands.subscribed", extra={"channels": channels})

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                envelope = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("redis_commands.bad_json", extra={"raw": raw})
                continue
            yield envelope
    finally:
        await pubsub.close()
        await client.aclose()
