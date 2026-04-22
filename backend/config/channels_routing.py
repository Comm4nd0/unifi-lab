"""WebSocket URL routing for Django Channels.

Phase 0: no consumers wired yet. Phase 1+ will register per-fleet and
per-device event consumers under `/ws/fleets/<id>/` and `/ws/devices/<id>/`.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver

websocket_urlpatterns: list[URLPattern | URLResolver] = []
