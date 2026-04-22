"""Inform session lifecycle — the wire-level conversation with a controller.

Phase 0 stub. Once pcaps are captured, this module will use the codec
in ``engine.protocol`` to frame + encrypt inform payloads and maintain
the heartbeat timer per real UniFi firmware behaviour.
"""

from __future__ import annotations

import logging

log = logging.getLogger("uvl.engine.inform_session")


class InformSession:
    HEARTBEAT_INTERVAL_SECONDS = 10  # Real firmware uses 10s; override per model.

    def __init__(self, controller_inform_url: str, *, verify_tls: bool = True) -> None:
        self.controller_inform_url = controller_inform_url
        self.verify_tls = verify_tls

    async def adopt(self) -> None:
        # TODO: implement adoption handshake (initial inform, key exchange, first cfg-update)
        raise NotImplementedError("Inform adoption not implemented until pcaps are available")

    async def heartbeat_once(self) -> None:
        # TODO: implement heartbeat inform exchange
        raise NotImplementedError("Inform heartbeat not implemented until pcaps are available")
