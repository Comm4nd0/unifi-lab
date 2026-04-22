"""Supervisor — orchestrates many VirtualDevice tasks under one asyncio loop.

Two sources of work:

1. Startup poll — on boot, we select every VirtualDevice in ``pending`` state
   and spawn a task for it.
2. Live commands — while running, we subscribe to Redis ``worker:commands:*``
   and react to ``spawn`` / ``force_inform`` / ``despawn`` envelopes.

In Phase 0 the spawned tasks just log a stub loop — no bytes are
transmitted until ``engine.protocol.codec`` is real.
"""

from __future__ import annotations

import asyncio
import logging

from .config import EngineConfig
from .redis_commands import CHANNEL_DEVICES, subscribe_worker_commands

log = logging.getLogger("uvl.engine.supervisor")


class Supervisor:
    def __init__(self, cfg: EngineConfig) -> None:
        self.cfg = cfg
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._command_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        log.info("supervisor.start", extra={"redis": self.cfg.redis_url.split("@")[-1]})
        self._command_task = asyncio.create_task(
            self._consume_commands(), name="supervisor.commands"
        )

    async def shutdown(self) -> None:
        self._stop.set()
        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                pass
        for mac, task in list(self._tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            log.info("supervisor.device.cancelled", extra={"mac": mac})
        self._tasks.clear()

    async def _consume_commands(self) -> None:
        try:
            async for envelope in subscribe_worker_commands(
                self.cfg.redis_url, channels=[CHANNEL_DEVICES]
            ):
                action = envelope.get("action")
                device_id = envelope.get("device_id")
                if not action or not device_id:
                    continue
                log.info(
                    "supervisor.command.received",
                    extra={"action": action, "device_id": device_id},
                )
                if action == "spawn":
                    await self._spawn_device(device_id)
                elif action == "despawn":
                    await self._despawn_device(device_id)
                elif action == "force_inform":
                    await self._force_inform(device_id)
                else:
                    log.warning("supervisor.command.unknown", extra={"action": action})
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("supervisor.commands.failed")

    async def _spawn_device(self, device_id: str) -> None:
        if device_id in self._tasks:
            return
        task = asyncio.create_task(self._run_device(device_id), name=f"device:{device_id}")
        self._tasks[device_id] = task

    async def _despawn_device(self, device_id: str) -> None:
        task = self._tasks.pop(device_id, None)
        if task:
            task.cancel()

    async def _force_inform(self, device_id: str) -> None:
        """Phase 0 stub — logs the request; no bytes sent."""
        log.info("supervisor.force_inform", extra={"device_id": device_id})

    async def _run_device(self, device_id: str) -> None:
        """Phase 0 stub device loop.

        Real implementation (once pcaps land): open inform session, exchange
        adoption, maintain heartbeat on ``InformSession.HEARTBEAT_INTERVAL_SECONDS``.
        """
        log.info("device.loop.start", extra={"device_id": device_id})
        try:
            while not self._stop.is_set():
                await asyncio.sleep(10)
                log.debug("device.loop.tick", extra={"device_id": device_id})
        except asyncio.CancelledError:
            log.info("device.loop.cancelled", extra={"device_id": device_id})
            raise
