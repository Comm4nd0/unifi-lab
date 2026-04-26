"""Inform session — drives one device's TNBU conversation with the controller.

Each spawned device task creates an InformSession and calls ``run_once()``
in a loop: build payload -> encode -> POST -> decode response -> handle
commands -> record exchange -> callback to Django.

The session records every exchange in the ``InformExchange`` table via
SQLAlchemy async and calls back to Django to update heartbeat timestamps.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..clients.django_api import DjangoApiClient
from ..crypto import decrypt
from ..db.models import ControllerTarget, InformExchange, VirtualDevice
from .codec import decode_inform, encode_inform
from .keys import DEFAULT_INFORM_KEY

log = logging.getLogger("uvl.engine.inform")


class InformSession:
    """Manages the inform protocol loop for a single virtual device."""

    def __init__(
        self,
        *,
        device_id: str,
        sessionmaker: async_sessionmaker[AsyncSession],
        django_client_factory: Any,  # callable returning DjangoApiClient
        stop_event: Any,  # asyncio.Event
    ) -> None:
        self.device_id = device_id
        self._sessionmaker = sessionmaker
        self._django_client_factory = django_client_factory
        self._stop = stop_event
        self._uptime_base = time.monotonic()
        self._cfg_version = "000000000000"
        self._exchange_count = 0

    async def _load_context(
        self,
    ) -> tuple[VirtualDevice | None, ControllerTarget | None]:
        """Load device + controller from DB."""
        async with self._sessionmaker() as session:
            dev = (
                await session.execute(
                    select(VirtualDevice).where(VirtualDevice.id == self.device_id)
                )
            ).scalar_one_or_none()
            if dev is None:
                return None, None
            if dev.controller_target_id is None:
                return dev, None
            ctrl = await session.get(ControllerTarget, dev.controller_target_id)
            return dev, ctrl

    def _build_payload(self, dev: VirtualDevice) -> dict[str, Any]:
        """Build the inform JSON payload mimicking a real UniFi device."""
        now = int(time.time())
        uptime = int(time.monotonic() - self._uptime_base)
        mac = dev.mac_address.replace(":", "").lower()

        return {
            "board_rev": 21,
            "bootrom_version": "unifi-v1.5.2",
            "cfgversion": self._cfg_version,
            "config_network_wan": {"type": "dhcp"},
            "connect_request_ip": f"10.0.0.{random.randint(2, 254)}",
            "connect_request_port": 0,
            "default": dev.state == "pending",
            "device_id": mac,
            "discovery_response": False,
            "firmware": dev.firmware_version or "7.0.83.15871",
            "guest_token": "0" * 32,
            "has_default_route_distance": True,
            "has_dns": True,
            "has_gateway": True,
            "hostname": dev.hostname or f"UVL-{mac[:8]}",
            "inform_as_notif": False,
            "inform_ip": f"10.0.0.{random.randint(2, 254)}",
            "inform_url": "",  # filled from controller
            "ip": f"10.0.0.{random.randint(2, 254)}",
            "isolated": False,
            "locating": False,
            "mac": dev.mac_address.lower(),
            "model": dev.model_code,
            "model_display": dev.model_code,
            "netmask": "255.255.255.0",
            "required_version": "2.0.0",
            "selfrun_guest_mode": "off",
            "serial": dev.serial_number,
            "state": 2 if dev.state == "pending" else 1,
            "time": now,
            "uptime": uptime,
            "version": dev.firmware_version or "7.0.83.15871",
        }

    async def run_once(self) -> str | None:
        """Execute one inform exchange.

        Returns the exchange_type string, or ``None`` when the device or
        controller cannot be loaded from the DB.
        """
        dev, ctrl = await self._load_context()
        if dev is None or ctrl is None:
            log.warning("inform.no_context", extra={"device_id": self.device_id})
            return None

        inform_url = decrypt(ctrl.inform_url)
        mac_bytes = bytes.fromhex(dev.mac_address.replace(":", ""))

        # Use device's stored key, falling back to the default pre-adoption key
        raw_key = decrypt(dev.inform_key) if dev.inform_key else ""
        if raw_key:
            try:
                key = bytes.fromhex(raw_key)
            except ValueError:
                key = DEFAULT_INFORM_KEY
        else:
            key = DEFAULT_INFORM_KEY

        payload = self._build_payload(dev)
        payload["inform_url"] = inform_url

        # Encode the inform frame
        frame_bytes = encode_inform(payload=payload, key=key, mac=mac_bytes)

        # POST to the controller's inform URL
        exchange_type = "heartbeat"
        payload_out: dict[str, Any] | None = None
        try:
            async with httpx.AsyncClient(
                verify=ctrl.verify_tls, timeout=15.0, follow_redirects=True
            ) as client:
                resp = await client.post(
                    inform_url,
                    content=frame_bytes,
                    headers={"Content-Type": "application/x-binary"},
                )
                if resp.status_code >= 400:
                    log.warning(
                        "inform.http_error",
                        extra={
                            "device_id": self.device_id,
                            "status": resp.status_code,
                            "body": resp.text[:200],
                        },
                    )
                    exchange_type = "error"
                else:
                    # Decode controller response
                    if resp.content:
                        try:
                            payload_out = decode_inform(resp.content, key=key)
                            cmd = payload_out.get("_type", "")
                            if cmd == "noop" or (
                                isinstance(payload_out.get("cmd"), str)
                                and payload_out["cmd"] == "noop"
                            ):
                                exchange_type = "heartbeat"
                            elif "mgmt_cfg" in payload_out:
                                exchange_type = "config_push"
                                self._cfg_version = str(
                                    payload_out.get("cfgversion", self._cfg_version)
                                )
                            elif payload_out.get("cmd") == "set-inform":
                                exchange_type = "adopt"
                        except Exception:
                            log.exception(
                                "inform.decode_failed",
                                extra={"device_id": self.device_id},
                            )
                            exchange_type = "error"
                            payload_out = {
                                "_raw_error": "decode failed",
                                "_status": resp.status_code,
                            }
        except httpx.TimeoutException:
            log.warning("inform.timeout", extra={"device_id": self.device_id})
            exchange_type = "error"
        except Exception:
            log.exception("inform.request_failed", extra={"device_id": self.device_id})
            exchange_type = "error"

        # Record the exchange in the DB
        self._exchange_count += 1
        now = datetime.now(UTC)
        async with self._sessionmaker() as session:
            session.add(
                InformExchange(
                    id=uuid.uuid4(),
                    device_id=uuid.UUID(self.device_id),
                    exchange_type=exchange_type,
                    payload_in=payload,
                    payload_out=payload_out,
                    exchanged_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        # Notify Django of heartbeat
        if exchange_type in ("heartbeat", "config_push"):
            try:
                django_client: DjangoApiClient = self._django_client_factory()
                await django_client.update_device_heartbeat(self.device_id)
            except Exception:
                log.debug(
                    "inform.heartbeat_callback_failed",
                    extra={"device_id": self.device_id},
                )

        log.info(
            "inform.exchange.ok",
            extra={
                "device_id": self.device_id,
                "type": exchange_type,
                "count": self._exchange_count,
            },
        )
        return exchange_type
