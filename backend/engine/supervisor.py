"""Supervisor — orchestrates many VirtualDevice tasks under one asyncio loop."""

from __future__ import annotations

import asyncio
import logging

from .config import EngineConfig

log = logging.getLogger("uvl.engine.supervisor")


class Supervisor:
    def __init__(self, cfg: EngineConfig) -> None:
        self.cfg = cfg
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        log.info("supervisor.start", extra={"db": self.cfg.database_url.split("@")[-1]})
        # Phase 0: no devices supervised yet. Phase 1 polls the DB for VirtualDevices
        # in state=pending and spawns a task per device.

    async def shutdown(self) -> None:
        for mac, task in list(self._tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            log.info("supervisor.device.cancelled", extra={"mac": mac})
        self._tasks.clear()
