"""Events — worker publishes domain events over Redis pub/sub for Django consumers."""

from __future__ import annotations

import json
import logging

log = logging.getLogger("uvl.engine.events")


async def publish_event(channel: str, payload: dict[str, object]) -> None:
    log.debug("event.publish", extra={"channel": channel, "payload": json.dumps(payload)})
    # TODO: redis.publish via a shared connection pool
