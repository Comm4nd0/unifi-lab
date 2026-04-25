"""Worker-side traffic ticker — the Phase 3 flow injection MVP.

Every ``tick_seconds`` we:
1. Read active ``TrafficProfile`` rows.
2. For each profile, resolve matching fleets (``applies_to.fleet_id`` when
   present, otherwise all fleets).
3. For each matched device, emit one ``FlowRecord`` per flow spec in the
   profile's ``parsed_json.flows`` list.

MVP simplifications (full Phase 3 per ``Components/25 - Traffic Simulator``
expands these):
- Rate parsing is intentionally naive — one flow per spec per tick.
- No controller-shadow firewall model; ``blocked`` is either whatever the
  flow spec declares, or a small random sprinkle for realism.
- Fixed app → DPI/port mapping inline; the real DPI tables land with Phase 3
  once we have captured inform payloads.
- Src IPs are drawn from 10.0.0.0/24; dst IPs are random public-ish octets.

Per-tick cap keeps runaway blueprints from filling Postgres — configurable
via ``TrafficTicker.per_tick_cap``.
"""

from __future__ import annotations

import contextlib
import logging
import random
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.sql import func

from .._time import utcnow
from ..db.models import FlowRecord, TrafficProfile, VirtualDevice
from .dpi import lookup_app as _dpi_lookup

log = logging.getLogger("uvl.engine.traffic")


def _resolve_proto_port(spec: dict[str, Any]) -> tuple[str, int | None]:
    app = str(spec.get("app") or "HTTPS")
    # DPI fixture is the authoritative source; explicit spec overrides win.
    _app_id, _cat_id, proto, port = _dpi_lookup(app)
    if "protocol" in spec:
        proto = str(spec["protocol"]).lower()
    if "port" in spec:
        with contextlib.suppress(TypeError, ValueError):
            port = int(spec["port"])
    return proto, port


def _random_client_ip(rng: random.Random) -> str:
    return f"10.0.0.{rng.randint(2, 254)}"


def _random_remote_ip(rng: random.Random) -> str:
    # Non-private-ish: avoid 10/8, 172.16/12, 192.168/16 for visual clarity.
    while True:
        a = rng.randint(1, 254)
        if a in (10, 127, 192, 172):
            continue
        return f"{a}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _byte_range(spec_value: str | None, rng: random.Random) -> int:
    """Parse values like '5KB-2MB' or '100-500' into a random int in range."""
    if not spec_value:
        return rng.randint(1_000, 500_000)
    try:
        lo_raw, hi_raw = spec_value.split("-")
    except ValueError:
        return rng.randint(1_000, 500_000)
    return rng.randint(_parse_bytes(lo_raw), _parse_bytes(hi_raw))


def _parse_bytes(token: str) -> int:
    token = token.strip().upper()
    mult = 1
    if token.endswith("KB"):
        mult, token = 1_000, token[:-2]
    elif token.endswith("MB"):
        mult, token = 1_000_000, token[:-2]
    elif token.endswith("GB"):
        mult, token = 1_000_000_000, token[:-2]
    try:
        return int(float(token) * mult)
    except ValueError:
        return 1_000


class TrafficTicker:
    """Periodic async task: generate FlowRecord rows for active profiles."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[Any],
        *,
        tick_seconds: float = 5.0,
        per_tick_cap: int = 200,
        rng: random.Random | None = None,
    ) -> None:
        self._sessionmaker = sessionmaker
        self.tick_seconds = tick_seconds
        self.per_tick_cap = per_tick_cap
        self._rng = rng or random.Random()

    async def tick_once(self) -> int:
        """One pass. Returns the number of flow rows generated."""
        generated: list[FlowRecord] = []
        async with self._sessionmaker() as session:
            profiles = (
                (await session.execute(select(TrafficProfile).where(TrafficProfile.is_active)))
                .scalars()
                .all()
            )
            if not profiles:
                return 0

            for profile in profiles:
                if len(generated) >= self.per_tick_cap:
                    break
                devices = await self._devices_for_profile(session, profile)
                flows: list[dict[str, Any]] = (profile.parsed_json or {}).get("flows", []) or []
                for device in devices:
                    for spec in flows:
                        if len(generated) >= self.per_tick_cap:
                            break
                        generated.append(self._build_flow(device, profile, spec))
                    if len(generated) >= self.per_tick_cap:
                        break
            session.add_all(generated)
            await session.commit()

        if generated:
            log.info(
                "traffic.tick.ok",
                extra={"generated": len(generated), "profiles": len(profiles)},
            )
        return len(generated)

    async def _devices_for_profile(
        self, session: Any, profile: TrafficProfile
    ) -> list[VirtualDevice]:
        applies = (profile.parsed_json or {}).get("applies_to") or {}
        fleet_id = applies.get("fleet_id") or applies.get("fleet")  # fleet may be id or legacy name
        stmt = select(VirtualDevice).where(VirtualDevice.fleet_id.is_not(None))
        if fleet_id:
            try:
                uuid.UUID(str(fleet_id))
                stmt = stmt.where(VirtualDevice.fleet_id == uuid.UUID(str(fleet_id)))
            except (ValueError, AttributeError):
                # Non-UUID fleet reference — treat as "no device matches"
                return []
        stmt = stmt.order_by(func.random()).limit(32)  # sample to keep ticks bounded
        return list((await session.execute(stmt)).scalars().all())

    def _build_flow(
        self, device: VirtualDevice, profile: TrafficProfile, spec: dict[str, Any]
    ) -> FlowRecord:
        proto, dst_port = _resolve_proto_port(spec)
        blocked = bool(spec.get("blocked")) or self._rng.random() < 0.05
        app_name = str(spec.get("app") or "HTTPS")
        byte_spec = spec.get("bytes_per_flow")
        tx = _byte_range(byte_spec, self._rng)
        rx = _byte_range(byte_spec, self._rng)
        now = utcnow()
        return FlowRecord(
            id=uuid.uuid4(),
            device_id=device.id,
            protocol=proto,
            src_ip=_random_client_ip(self._rng),
            dst_ip=_random_remote_ip(self._rng),
            src_port=self._rng.randint(32_000, 65_000),
            dst_port=dst_port,
            bytes_tx=tx,
            bytes_rx=rx,
            application=app_name,
            reported_at=now,
            blocked=blocked,
            created_at=now,
            updated_at=now,
        )


async def run_ticker_loop(ticker: TrafficTicker, stop_event: Any) -> None:
    """Drive ``ticker`` until ``stop_event`` is set. Swallows per-tick errors."""
    import asyncio

    while not stop_event.is_set():
        try:
            await ticker.tick_once()
        except Exception:
            log.exception("traffic.tick.failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=ticker.tick_seconds)
        except TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
    _ = timedelta  # keep typing import warm
