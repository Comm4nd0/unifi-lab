"""WebSocket URL routing for Django Channels.

- /ws/devices/<device_id>/inform — tail of inform exchanges for a device.
- /ws/fleets/<fleet_id>/          — fleet lifecycle events (state changes,
                                     device-state transitions, ramp progress).
- /ws/cluster/                    — cluster-wide fan-out (copy of every fleet
                                     event, used by the dashboard for live
                                     query invalidation).
- /ws/traffic/<fleet_id>/         — live traffic flow stream for a fleet.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, re_path

from apps.devices.consumers import DeviceInformConsumer
from apps.firmware.consumers import FirmwareProgressConsumer
from apps.fleets.cluster_consumer import ClusterConsumer
from apps.fleets.consumers import FleetConsumer
from apps.traffic.consumers import TrafficFlowConsumer

websocket_urlpatterns: list[URLPattern | URLResolver] = [
    re_path(
        r"^ws/devices/(?P<device_id>[0-9a-f-]{36})/inform/?$",
        DeviceInformConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/fleets/(?P<fleet_id>[0-9a-f-]{36})/?$",
        FleetConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/cluster/?$",
        ClusterConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/firmware/(?P<blob_id>[0-9a-f-]{36})/?$",
        FirmwareProgressConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/traffic/(?P<fleet_id>[0-9a-f-]{36})/?$",
        TrafficFlowConsumer.as_asgi(),
    ),
]
