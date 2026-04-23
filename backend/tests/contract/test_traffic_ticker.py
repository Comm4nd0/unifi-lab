"""Traffic ticker — MVP flow injection loop.

These tests use duck-typed fakes for the SQLAlchemy session rather than
spinning up Postgres. The ticker only calls ``session.execute`` (for the
active-profile fetch) and ``session.add_all`` + ``session.commit`` for
writes, so a small async context manager is enough to cover the shape.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from engine.traffic.ticker import (
    TrafficTicker,
    _byte_range,
    _parse_bytes,
    _resolve_proto_port,
    run_ticker_loop,
)

# --- fakes -----------------------------------------------------------------


class _FakeProfile:
    """Duck-typed stand-in for ``TrafficProfile`` SQLAlchemy row."""

    def __init__(
        self,
        *,
        flows: list[dict[str, Any]] | None = None,
        applies_to: dict[str, Any] | None = None,
        name: str = "p",
    ) -> None:
        self.id = uuid.uuid4()
        self.name = name
        parsed: dict[str, Any] = {}
        if flows is not None:
            parsed["flows"] = flows
        if applies_to is not None:
            parsed["applies_to"] = applies_to
        self.parsed_json = parsed


class _FakeDevice:
    """Duck-typed stand-in for ``VirtualDevice`` SQLAlchemy row."""

    def __init__(self, *, fleet_id: uuid.UUID | None = None) -> None:
        self.id = uuid.uuid4()
        self.fleet_id = fleet_id or uuid.uuid4()


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)


class _FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._items)


class _FakeSession:
    """Minimal async session: profile query + writes go through here."""

    def __init__(self, profiles: list[_FakeProfile]) -> None:
        self._profiles = profiles
        self.added: list[Any] = []
        self.commits = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def execute(self, _stmt: Any) -> _FakeResult:
        # The only ``execute`` the ticker makes inside tick_once directly is
        # the active-profile fetch; device queries are intercepted via
        # ``_devices_for_profile`` override in these tests.
        return _FakeResult(self._profiles)

    def add_all(self, rows: list[Any]) -> None:
        self.added.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


def _sessionmaker_for(profiles: list[_FakeProfile]) -> tuple[Any, _FakeSession]:
    session = _FakeSession(profiles)

    def factory() -> _FakeSession:
        return session

    return factory, session


def _ticker_with(
    profiles: list[_FakeProfile],
    *,
    devices: list[_FakeDevice] | None = None,
    per_tick_cap: int = 200,
    seed: int = 1,
) -> tuple[TrafficTicker, _FakeSession]:
    factory, session = _sessionmaker_for(profiles)
    ticker = TrafficTicker(
        factory,
        tick_seconds=0.01,
        per_tick_cap=per_tick_cap,
        rng=random.Random(seed),
    )
    ticker._devices_for_profile = AsyncMock(return_value=list(devices or []))  # type: ignore[method-assign]
    return ticker, session


# --- pure helpers ----------------------------------------------------------


def test_parse_bytes_units() -> None:
    assert _parse_bytes("5KB") == 5_000
    assert _parse_bytes("2MB") == 2_000_000
    assert _parse_bytes("1GB") == 1_000_000_000
    assert _parse_bytes("250") == 250
    assert _parse_bytes("garbage") == 1_000  # safe fallback


def test_byte_range_respects_bounds() -> None:
    rng = random.Random(1)
    value = _byte_range("100-500", rng)
    assert 100 <= value <= 500


def test_byte_range_bad_input_falls_back() -> None:
    rng = random.Random(1)
    # No dash → takes the catch-all range; still a plausible int.
    value = _byte_range("nope", rng)
    assert 1_000 <= value <= 500_000


def test_resolve_proto_port_known_app() -> None:
    assert _resolve_proto_port({"app": "HTTPS"}) == ("tcp", 443)
    assert _resolve_proto_port({"app": "DNS"}) == ("udp", 53)


def test_resolve_proto_port_unknown_app_falls_back_to_https() -> None:
    assert _resolve_proto_port({"app": "Something-Made-Up"}) == ("tcp", 443)


def test_resolve_proto_port_explicit_overrides_win() -> None:
    assert _resolve_proto_port({"app": "HTTPS", "protocol": "udp", "port": 8443}) == ("udp", 8443)


# --- tick_once behaviour ---------------------------------------------------


@pytest.mark.asyncio
async def test_no_profiles_yields_no_rows() -> None:
    ticker, session = _ticker_with([])
    generated = await ticker.tick_once()
    assert generated == 0
    assert session.added == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_profile_without_flows_yields_no_rows() -> None:
    ticker, session = _ticker_with(
        [_FakeProfile(flows=[])],
        devices=[_FakeDevice()],
    )
    assert await ticker.tick_once() == 0
    assert session.added == []
    # The tick still commits the (empty) batch — cheap and keeps the
    # code path uniform; the assertion pins the behaviour.
    assert session.commits == 1


@pytest.mark.asyncio
async def test_profile_generates_one_flow_per_spec_per_device() -> None:
    devices = [_FakeDevice(), _FakeDevice()]
    profile = _FakeProfile(flows=[{"app": "HTTPS"}, {"app": "DNS"}])
    ticker, session = _ticker_with([profile], devices=devices)

    generated = await ticker.tick_once()

    # 2 devices * 2 specs = 4 rows.
    assert generated == 4
    assert len(session.added) == 4
    assert session.commits == 1

    # Every row references one of the provided devices and carries the
    # expected protocol/port based on the spec's app.
    device_ids = {d.id for d in devices}
    assert all(row.device_id in device_ids for row in session.added)
    by_app = {row.application for row in session.added}
    assert by_app == {"HTTPS", "DNS"}


@pytest.mark.asyncio
async def test_per_tick_cap_truncates_generated_flows() -> None:
    # 10 devices * 5 specs = 50 potential rows; cap at 7.
    devices = [_FakeDevice() for _ in range(10)]
    profile = _FakeProfile(flows=[{"app": "HTTPS"} for _ in range(5)])
    ticker, session = _ticker_with([profile], devices=devices, per_tick_cap=7)

    generated = await ticker.tick_once()

    assert generated == 7
    assert len(session.added) == 7


@pytest.mark.asyncio
async def test_explicit_blocked_spec_stays_blocked() -> None:
    profile = _FakeProfile(flows=[{"app": "HTTPS", "blocked": True}])
    ticker, session = _ticker_with([profile], devices=[_FakeDevice()])
    await ticker.tick_once()
    assert session.added[0].blocked is True


@pytest.mark.asyncio
async def test_flow_byte_counts_honor_spec_range() -> None:
    profile = _FakeProfile(flows=[{"app": "HTTPS", "bytes_per_flow": "100-200"}])
    ticker, session = _ticker_with([profile], devices=[_FakeDevice()])
    await ticker.tick_once()
    row = session.added[0]
    assert 100 <= row.bytes_tx <= 200
    assert 100 <= row.bytes_rx <= 200


@pytest.mark.asyncio
async def test_tick_passes_profile_to_device_resolver() -> None:
    profile = _FakeProfile(flows=[{"app": "HTTPS"}], applies_to={"fleet_id": "abc"})
    ticker, _session = _ticker_with([profile], devices=[_FakeDevice()])
    await ticker.tick_once()
    # The resolver is the one that decides which devices a profile covers.
    # Here we just assert it was invoked once per profile with the profile
    # object — the real SQL filter is exercised in integration.
    ticker._devices_for_profile.assert_awaited_once()  # type: ignore[attr-defined]
    args, _kwargs = ticker._devices_for_profile.call_args  # type: ignore[attr-defined]
    assert args[1] is profile


# --- run_ticker_loop -------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ticker_loop_exits_when_stop_event_set() -> None:
    """Setting the stop event must cleanly exit the loop, not hang."""
    ticker, _session = _ticker_with([])
    stop = asyncio.Event()
    stop.set()  # pre-set so the loop exits after one iteration.

    # Guard with a timeout — a regression here would hang the suite.
    await asyncio.wait_for(run_ticker_loop(ticker, stop), timeout=1.0)


@pytest.mark.asyncio
async def test_run_ticker_loop_swallows_per_tick_exceptions() -> None:
    """A tick that raises should be logged and the loop should keep going."""
    ticker, _session = _ticker_with([])
    tick_calls = 0

    async def flaky_tick() -> int:
        nonlocal tick_calls
        tick_calls += 1
        if tick_calls == 1:
            raise RuntimeError("boom")
        return 0

    ticker.tick_once = flaky_tick  # type: ignore[method-assign]
    stop = asyncio.Event()

    async def stopper() -> None:
        # Let two ticks fire, then stop.
        await asyncio.sleep(0.05)
        stop.set()

    await asyncio.wait_for(
        asyncio.gather(run_ticker_loop(ticker, stop), stopper()),
        timeout=1.0,
    )
    assert tick_calls >= 2
