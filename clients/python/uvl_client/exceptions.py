"""Exception hierarchy for the UVL Python client."""
from __future__ import annotations

from typing import Any


class UVLError(Exception):
    """Base class for all UVL client errors."""

    def __init__(self, message: str, *, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class UVLAuthError(UVLError):
    """Authentication failed or the refresh token is invalid/expired."""


class UVLTimeout(UVLError):
    """A ``wait_for_state`` call exceeded its timeout budget."""
