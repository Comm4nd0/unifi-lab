"""VirtualDevice — the worker-side runtime for a single simulated device."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .inform_session import InformSession
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
        self._session: InformSession | None = None

    def _mac_bytes(self) -> bytes:
        return bytes.fromhex(self.spec.mac_address.replace(":", ""))

    def _transition(self, to: DeviceState) -> None:
        if not can_transition(self.state, to):
            raise RuntimeError(f"Illegal transition {self.state} -> {to}")
        log.info(
            "device.transition", extra={"mac": self.spec.mac_address, "from": self.state, "to": to}
        )
        self.state = to

    async def connect(self) -> None:
        """Open the inform session with the controller and send the initial inform."""
        self._transition(DeviceState.KEY_EXCHANGE)
        self._session = InformSession(
            self.spec.controller_inform_url,
            mac=self._mac_bytes(),
            model=self.spec.model_code,
            serial=self.spec.serial_number,
            firmware=self.spec.firmware_version,
            verify_tls=self.spec.verify_tls,
        )
        resp = await self._session.adopt()
        rtype = resp.get("_type", "noop")
        log.info("device.connect.ok  rtype=%s mac=%s", rtype, self.spec.mac_address)
        self._transition(DeviceState.HEARTBEAT)

    async def heartbeat(self) -> None:
        if self._session is None:
            raise RuntimeError("connect() must be called before heartbeat()")
        resp = await self._session.heartbeat_once()
        rtype = resp.get("_type", "noop")
        log.debug("device.heartbeat  rtype=%s mac=%s", rtype, self.spec.mac_address)
        if rtype in ("setparam", "setdefault"):
            await self.apply_config(resp)

    async def apply_config(self, config: dict[str, Any]) -> None:
        self._transition(DeviceState.CONFIG_APPLY)
        log.info(
            "device.config_apply  mac=%s keys=%s",
            self.spec.mac_address,
            list(config.keys()),
        )
        self._transition(DeviceState.HEARTBEAT)

    async def disconnect(self) -> None:
        self._transition(DeviceState.DISCONNECTED)
        self._session = None
