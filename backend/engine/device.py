"""VirtualDevice — the worker-side runtime for a single simulated device."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .state_machine import DeviceState, can_transition

log = logging.getLogger("uvl.engine.device")


@dataclass
class VirtualDeviceSpec:
    """Everything the worker needs to instantiate a device.

    Comes from Django via the clients.django_api layer or, in the Phase 0
    smoke-test, from CLI arguments directly.
    """

    mac_address: str
    serial_number: str
    model_code: str
    firmware_version: str
    controller_inform_url: str
    verify_tls: bool = True


class VirtualDevice:
    def __init__(self, spec: VirtualDeviceSpec) -> None:
        self.spec = spec
        self.state = DeviceState.PENDING

    def _transition(self, to: DeviceState) -> None:
        if not can_transition(self.state, to):
            raise RuntimeError(f"Illegal transition {self.state} -> {to}")
        log.info(
            "device.transition", extra={"mac": self.spec.mac_address, "from": self.state, "to": to}
        )
        self.state = to

    async def connect(self) -> None:
        """Open the inform session (key exchange) with the controller.

        Phase 0 stub: logs the flow, doesn't transmit. Real AES + TNBU
        implementation in ``engine.protocol``.
        """
        log.info("[would send] initial inform frame", extra={"mac": self.spec.mac_address})
        self._transition(DeviceState.KEY_EXCHANGE)
        log.info(
            "[would expect] controller key exchange response",
            extra={"mac": self.spec.mac_address},
        )
        self._transition(DeviceState.HEARTBEAT)

    async def heartbeat(self) -> None:
        log.info("[would send] heartbeat inform", extra={"mac": self.spec.mac_address})

    async def apply_config(self, config: dict[str, object]) -> None:
        self._transition(DeviceState.CONFIG_APPLY)
        log.info(
            "[would apply] config push",
            extra={"mac": self.spec.mac_address, "keys": list(config.keys())},
        )
        self._transition(DeviceState.HEARTBEAT)

    async def disconnect(self) -> None:
        self._transition(DeviceState.DISCONNECTED)
