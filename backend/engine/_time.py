"""Tiny time helper so tests can monkeypatch one call site."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
