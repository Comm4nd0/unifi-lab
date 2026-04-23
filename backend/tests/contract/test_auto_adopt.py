"""Worker auto-adopt flow — uses an injected fake client, no live backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.clients.unifi import UnifiApiError
from engine.config import EngineConfig
from engine.supervisor import Supervisor


def _cfg() -> EngineConfig:
    return EngineConfig(
        database_url="postgresql://x:x@localhost/x",
        redis_url="redis://localhost/0",
        channels_layer_url="redis://localhost/2",
        django_api_base="http://localhost:8003",
        log_level="INFO",
    )


class _FakeCtrl:
    """A minimal stand-in for the SQLAlchemy ControllerTarget row.

    Using a plain attribute bag instead of the ORM class avoids SQLAlchemy
    descriptor plumbing, which doesn't initialise on ``__new__``. The
    supervisor path only reads these attributes, so duck-typing is fine.
    """

    def __init__(self) -> None:
        self.id = "00000000-0000-0000-0000-000000000001"
        self.name = "Lab"
        self.kind = "uos-server"
        self.inform_url = "https://lab.test:443"
        self.api_url = "https://lab.test:443/api"
        self.api_username = "admin"
        self.api_password = "pw"
        self.verify_tls = False
        self.is_active = True
        self.health = "unknown"


class _FakeClient:
    """Async context manager that records which methods were called."""

    def __init__(
        self,
        *,
        login_error: Exception | None = None,
        adopt_error: Exception | None = None,
        adopt_error_on_attempt: int | None = None,
    ) -> None:
        self.login_error = login_error
        self.adopt_error = adopt_error
        self.adopt_error_on_attempt = adopt_error_on_attempt
        self.login_calls = 0
        self.adopt_calls: list[str] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def login(self) -> None:
        self.login_calls += 1
        if self.login_error is not None:
            raise self.login_error

    async def adopt(self, mac: str) -> None:
        self.adopt_calls.append(mac)
        attempt = len(self.adopt_calls)
        if self.adopt_error is not None and (
            self.adopt_error_on_attempt is None or attempt <= self.adopt_error_on_attempt
        ):
            raise self.adopt_error


async def _invoke_adopt(
    supervisor: Supervisor, fake: _FakeClient, mac: str = "02:00:00:aa:bb:cc"
) -> None:
    ctrl = _FakeCtrl()
    supervisor.client_factory = lambda c: fake  # type: ignore[assignment]
    supervisor._load_adopt_context = AsyncMock(return_value=(mac, ctrl))  # type: ignore[method-assign]
    await supervisor._auto_adopt_device("dev-1")


@pytest.mark.asyncio
async def test_happy_path_calls_login_then_adopt(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    sup = Supervisor(_cfg())
    fake = _FakeClient()
    await _invoke_adopt(sup, fake)
    assert fake.login_calls == 1
    assert fake.adopt_calls == ["02:00:00:aa:bb:cc"]
    await sup.shutdown()


@pytest.mark.asyncio
async def test_client_error_is_not_retried(monkeypatch):  # type: ignore[no-untyped-def]
    sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep)
    sup = Supervisor(_cfg())
    fake = _FakeClient(adopt_error=UnifiApiError(403, "forbidden"))
    await _invoke_adopt(sup, fake)
    assert fake.login_calls == 1  # only one attempt total
    assert fake.adopt_calls == ["02:00:00:aa:bb:cc"]
    assert sleep.await_count == 0
    await sup.shutdown()


@pytest.mark.asyncio
async def test_transient_server_error_retries_then_succeeds(monkeypatch):  # type: ignore[no-untyped-def]
    sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep)
    sup = Supervisor(_cfg())
    # Fail the first two adopt calls (5xx), succeed on the third.
    fake = _FakeClient(adopt_error=UnifiApiError(503, "busy"), adopt_error_on_attempt=2)
    await _invoke_adopt(sup, fake)
    assert len(fake.adopt_calls) == 3
    assert sleep.await_count == 2  # backoff between attempts 1-2 and 2-3
    await sup.shutdown()


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    sup = Supervisor(_cfg())
    fake = _FakeClient(adopt_error=UnifiApiError(503, "busy"))
    await _invoke_adopt(sup, fake)
    assert len(fake.adopt_calls) == 4  # AUTO_ADOPT_MAX_ATTEMPTS
    await sup.shutdown()


@pytest.mark.asyncio
async def test_skipped_when_no_controller_target(monkeypatch):  # type: ignore[no-untyped-def]
    sup = Supervisor(_cfg())
    called = MagicMock()
    sup.client_factory = called  # type: ignore[assignment]
    sup._load_adopt_context = AsyncMock(return_value=("mac", None))  # type: ignore[method-assign]
    await sup._auto_adopt_device("dev-1")
    called.assert_not_called()
    await sup.shutdown()


@pytest.mark.asyncio
async def test_skipped_when_device_missing(monkeypatch):  # type: ignore[no-untyped-def]
    sup = Supervisor(_cfg())
    called = MagicMock()
    sup.client_factory = called  # type: ignore[assignment]
    sup._load_adopt_context = AsyncMock(return_value=(None, None))  # type: ignore[method-assign]
    await sup._auto_adopt_device("dev-missing")
    called.assert_not_called()
    await sup.shutdown()
