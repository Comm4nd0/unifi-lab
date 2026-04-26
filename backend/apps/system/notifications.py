"""Lightweight notification subsystem backed by Django's cache.

Avoids a new DB model/migration — stores the last N notifications in
a cache key with a 24-hour TTL. For v1 the cache is the only store;
if persistence across cache evictions matters later, a migration to a
real model is straightforward.

Notifications are also published to the ``cluster`` channel group for
real-time delivery — the frontend's NotificationBell subscribes there.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from django.core.cache import cache

log = logging.getLogger("uvl.notifications")

CACHE_KEY = "uvl:notifications"
MAX_ITEMS = 50
TTL_SECONDS = 24 * 60 * 60  # 24h

# Notification levels
LEVEL_INFO = "info"
LEVEL_SUCCESS = "success"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"


def push(
    *,
    title: str,
    message: str = "",
    level: str = LEVEL_INFO,
    target_type: str = "",
    target_id: str = "",
) -> dict[str, Any]:
    """Create a notification and broadcast it.

    Returns the created notification dict.
    """
    notification = {
        "id": str(uuid.uuid4()),
        "title": title,
        "message": message,
        "level": level,
        "target_type": target_type,
        "target_id": target_id,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Append to cache list (newest first)
    items: list[dict[str, Any]] = cache.get(CACHE_KEY) or []
    items.insert(0, notification)
    items = items[:MAX_ITEMS]
    cache.set(CACHE_KEY, items, TTL_SECONDS)

    # Broadcast to WS cluster group
    _broadcast(notification)

    return notification


def list_all() -> list[dict[str, Any]]:
    """Return all cached notifications, newest first."""
    return cache.get(CACHE_KEY) or []


def mark_read(notification_id: str) -> bool:
    """Mark a single notification as read. Returns True if found."""
    items: list[dict[str, Any]] = cache.get(CACHE_KEY) or []
    for item in items:
        if item["id"] == notification_id:
            item["read"] = True
            cache.set(CACHE_KEY, items, TTL_SECONDS)
            return True
    return False


def mark_all_read() -> int:
    """Mark all notifications as read. Returns count marked."""
    items: list[dict[str, Any]] = cache.get(CACHE_KEY) or []
    count = 0
    for item in items:
        if not item["read"]:
            item["read"] = True
            count += 1
    if count:
        cache.set(CACHE_KEY, items, TTL_SECONDS)
    return count


def dismiss(notification_id: str) -> bool:
    """Remove a notification entirely. Returns True if found."""
    items: list[dict[str, Any]] = cache.get(CACHE_KEY) or []
    original_len = len(items)
    items = [i for i in items if i["id"] != notification_id]
    if len(items) < original_len:
        cache.set(CACHE_KEY, items, TTL_SECONDS)
        return True
    return False


def clear_all() -> None:
    """Remove all notifications."""
    cache.delete(CACHE_KEY)


def unread_count() -> int:
    """Count of unread notifications."""
    items: list[dict[str, Any]] = cache.get(CACHE_KEY) or []
    return sum(1 for i in items if not i["read"])


def _broadcast(notification: dict[str, Any]) -> None:
    """Push to the cluster WS group for real-time delivery."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        envelope = {
            "v": 1,
            "type": "notification.created",
            "ts": notification["created_at"],
            "data": notification,
        }
        async_to_sync(layer.group_send)(
            "cluster",
            {"type": "notification.event", "payload": envelope},
        )
    except Exception:
        log.exception("notification.broadcast_failed")
