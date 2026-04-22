"""Worker-command publisher.

Django services call ``publish_worker_command(channel, **payload)`` to hand
work to the asyncio device engine. The publish runs via
``transaction.on_commit`` so commands are never sent for rows that end up
rolled back. Transport is Redis pub/sub on channels ``worker:commands:*``.

The engine side subscribes in ``engine.redis_commands``; never import back
across the process boundary.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction

log = logging.getLogger("uvl.worker_commands")

CHANNEL_DEVICES = "worker:commands:devices"
CHANNEL_FLEETS = "worker:commands:fleets"


def _redis_client():  # type: ignore[no-untyped-def]
    """Lazy import so tests that don't exercise Redis don't need it running."""
    import redis

    url = getattr(settings, "UVL_COMMANDS_REDIS_URL", None) or getattr(
        settings, "CELERY_BROKER_URL", "redis://localhost:6379/1"
    )
    return redis.from_url(url)


def _publish_now(channel: str, payload: dict[str, Any]) -> None:
    try:
        client = _redis_client()
        client.publish(channel, json.dumps(payload, default=str))
        log.debug("worker_command.published", extra={"channel": channel, "payload": payload})
    except Exception:
        # Publishing must not break the request — the supervisor also polls
        # the DB on a tick, so a missed pub/sub message is recoverable.
        log.exception("worker_command.publish_failed")


def publish_worker_command(channel: str, **payload: Any) -> None:
    """Queue a command for the engine once the current DB transaction commits.

    Outside a transaction (e.g. scripts), it publishes immediately.
    """
    envelope = {"channel": channel, **payload}
    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(lambda: _publish_now(channel, envelope))
    else:
        _publish_now(channel, envelope)
