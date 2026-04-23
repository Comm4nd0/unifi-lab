"""Fan-out of fleet lifecycle events onto the Channels layer.

Any state change worth streaming to subscribed clients (``/ws/fleets/<id>/``)
lands here. Keeps ``services.py`` and the Celery tasks free of channel-layer
details — they just call ``publish_fleet_event(fleet_id, type, **data)``.

Channel group name uses ``.`` not ``:`` (Channels' group-name validator
rejects colons). The matching consumer lives in ``apps.fleets.consumers``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

log = logging.getLogger("uvl.fleets.events")


def group_name(fleet_id: str) -> str:
    return f"fleet.{fleet_id}"


def _envelope(type_: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": type_,
        "ts": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


def publish_fleet_event(fleet_id: str, event_type: str, **data: Any) -> None:
    """Emit ``{type, ts, data}`` to the fleet's channel group.

    Swallows every error so an event publish never breaks the caller's
    transaction. In tests with no configured channel layer this is a no-op.
    """
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            group_name(fleet_id),
            {"type": "fleet.event", "payload": _envelope(event_type, data)},
        )
    except Exception:
        log.exception("publish_fleet_event.failed", extra={"fleet_id": fleet_id})
