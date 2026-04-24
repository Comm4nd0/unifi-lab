"""Heartbeat-only engine process — ``python -m engine.scripts.heartbeat_only``.

Minimal entry point for development and the preview shell: runs the
heartbeat loop against Django without the supervisor's Postgres and
Redis dependencies. Useful when you want the dashboard's "Engine"
tile to go green without standing up the full stack.

Production always uses ``python -m engine.main`` which brings the
supervisor online, traffic ticker, Redis command consumer, etc.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path

from ..clients.django_api import DjangoApiClient
from ..config import EngineConfig

log = logging.getLogger("uvl.engine.heartbeat")

INTERVAL_SECONDS = 30


def _load_dotenv_if_present() -> None:
    """Populate env from a repo-root ``.env`` so dev shells don't need to.

    Walks upward from this file until it finds an ``.env`` or a
    ``.git`` directory. Only sets vars that aren't already in
    ``os.environ`` — anything set explicitly in the calling shell
    wins. No-op when the file is absent.
    """
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            break
        if (candidate / ".git").exists():
            env_file = candidate / ".env"
            break
    else:
        return
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


async def _run() -> None:
    _load_dotenv_if_present()
    cfg = EngineConfig.from_env()
    logging.basicConfig(level=cfg.log_level)
    if not cfg.worker_token:
        log.error("UVL_WORKER_TOKEN is not set — Django will reject heartbeats.")
        return

    client = DjangoApiClient(base_url=cfg.django_api_base, token=cfg.worker_token)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop(*_: object) -> None:
        log.info("heartbeat-only shutdown requested")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        # Windows doesn't wire add_signal_handler for every signal.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    metadata = {"pid": os.getpid(), "mode": "heartbeat-only"}
    log.info("heartbeat-only start", extra={"api": cfg.django_api_base})
    while not stop.is_set():
        try:
            await client.send_heartbeat(metadata)
            log.debug("heartbeat.ok")
        except Exception:
            log.exception("heartbeat.failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SECONDS)
        except TimeoutError:
            continue
    log.info("heartbeat-only exit")


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run())


if __name__ == "__main__":
    main()
