"""Async Python client for UniFi Virtual Lab (UVL).

Typical usage::

    from uvl_client import UVLClient

    async with UVLClient("https://uvl.example.com", email=E, password=P) as uvl:
        fleet = await uvl.fleets.create(
            name=f"ci-{run_id}",
            controller_target_id=CONTROLLER_ID,
            blueprint_id=BLUEPRINT_ID,
        )
        await uvl.fleets.wait_for_state(fleet["id"], "ramping", timeout=30)
        ...
        await uvl.fleets.teardown(fleet["id"])

Both username/password and ``token`` (JWT access) auth are supported.
"""
from __future__ import annotations

from .client import UVLClient
from .exceptions import UVLAuthError, UVLError, UVLTimeout
from .types import (
    Blueprint,
    ControllerTarget,
    Fleet,
    Paginated,
    VirtualDevice,
)

__all__ = [
    "Blueprint",
    "ControllerTarget",
    "Fleet",
    "Paginated",
    "UVLAuthError",
    "UVLClient",
    "UVLError",
    "UVLTimeout",
    "VirtualDevice",
]

__version__ = "0.1.0"
