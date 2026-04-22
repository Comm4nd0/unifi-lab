"""Engine entry point — ``python -m engine.main``.

Boots the asyncio event loop, connects to Postgres + Redis, and starts the
supervisor which in turn manages individual VirtualDevice tasks.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from .config import EngineConfig
from .supervisor import Supervisor

log = logging.getLogger("uvl.engine")


async def _run() -> None:
    cfg = EngineConfig.from_env()
    logging.basicConfig(level=cfg.log_level)
    supervisor = Supervisor(cfg)
    await supervisor.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop(*_: object) -> None:
        log.info("engine shutdown requested")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    await stop.wait()
    await supervisor.shutdown()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
