"""Config applier — takes a config blob from the controller and mutates device state."""

from __future__ import annotations

import logging

log = logging.getLogger("uvl.engine.config_applier")


async def apply_config(mac: str, config: dict[str, object]) -> None:
    log.info("config.apply", extra={"mac": mac, "keys": list(config.keys())})
    # TODO: translate controller config blob into device state changes (VLANs, WLANs, etc.)
