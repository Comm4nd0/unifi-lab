"""In-memory device state machine.

Mirrors the state enum on ``apps.devices.models.VirtualDevice.STATE_CHOICES``
but lives in the worker's memory — Django only sees checkpoint updates.
"""

from __future__ import annotations

from enum import Enum


class DeviceState(str, Enum):
    PENDING = "pending"
    KEY_EXCHANGE = "key_exchange"
    HEARTBEAT = "heartbeat"
    CONFIG_APPLY = "config_apply"
    ADOPTED = "adopted"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# Allowed transitions; the supervisor enforces these.
TRANSITIONS: dict[DeviceState, set[DeviceState]] = {
    DeviceState.PENDING: {DeviceState.KEY_EXCHANGE, DeviceState.ERROR},
    DeviceState.KEY_EXCHANGE: {DeviceState.HEARTBEAT, DeviceState.ERROR, DeviceState.DISCONNECTED},
    DeviceState.HEARTBEAT: {
        DeviceState.CONFIG_APPLY,
        DeviceState.ADOPTED,
        DeviceState.DISCONNECTED,
        DeviceState.ERROR,
    },
    DeviceState.CONFIG_APPLY: {DeviceState.HEARTBEAT, DeviceState.ERROR},
    DeviceState.ADOPTED: {DeviceState.HEARTBEAT, DeviceState.DISCONNECTED, DeviceState.ERROR},
    DeviceState.DISCONNECTED: {DeviceState.KEY_EXCHANGE},
    DeviceState.ERROR: set(),
}


def can_transition(from_state: DeviceState, to_state: DeviceState) -> bool:
    return to_state in TRANSITIONS.get(from_state, set())
