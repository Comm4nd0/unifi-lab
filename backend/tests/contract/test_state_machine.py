from __future__ import annotations

import pytest

from engine.state_machine import DeviceState, can_transition


@pytest.mark.parametrize(
    "src,dst,allowed",
    [
        (DeviceState.PENDING, DeviceState.KEY_EXCHANGE, True),
        (DeviceState.PENDING, DeviceState.HEARTBEAT, False),
        (DeviceState.KEY_EXCHANGE, DeviceState.HEARTBEAT, True),
        (DeviceState.HEARTBEAT, DeviceState.CONFIG_APPLY, True),
        (DeviceState.CONFIG_APPLY, DeviceState.HEARTBEAT, True),
        (DeviceState.ERROR, DeviceState.HEARTBEAT, False),
    ],
)
def test_can_transition(src: DeviceState, dst: DeviceState, allowed: bool) -> None:
    assert can_transition(src, dst) is allowed
