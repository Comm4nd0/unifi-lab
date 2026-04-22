"""WebSocket URL routing for Django Channels.

- /ws/devices/<device_id>/inform — tail of inform exchanges for a single device.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, re_path

from apps.devices.consumers import DeviceInformConsumer

websocket_urlpatterns: list[URLPattern | URLResolver] = [
    re_path(
        r"^ws/devices/(?P<device_id>[0-9a-f-]{36})/inform/?$",
        DeviceInformConsumer.as_asgi(),
    ),
]
