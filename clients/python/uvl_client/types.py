"""TypedDict shapes for UVL REST responses.

Stays deliberately loose: we don't want the client to break on
additive API changes. Use these as `dict`-shaped hints when annotating;
they're not runtime-validated.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar, TypedDict

T = TypeVar("T")


class Paginated(TypedDict, Generic[T]):
    count: int
    next: str | None
    previous: str | None
    results: list[T]


class ControllerTarget(TypedDict, total=False):
    id: str
    name: str
    kind: str
    inform_url: str
    api_url: str
    verify_tls: bool
    is_active: bool
    health: str
    last_verified_at: str | None
    created_at: str
    updated_at: str


class VirtualDevice(TypedDict, total=False):
    id: str
    mac_address: str
    serial_number: str
    model_code: str
    firmware_version: str
    hostname: str
    state: str
    controller_target: str | None
    fleet: str | None
    last_heartbeat_at: str | None
    last_config_applied_at: str | None
    created_at: str
    updated_at: str


class Blueprint(TypedDict, total=False):
    id: str
    name: str
    source_yaml: str
    parsed_json: dict[str, Any]
    version: int
    is_active: bool
    created_by: str | None
    created_at: str
    updated_at: str


class Fleet(TypedDict, total=False):
    id: str
    name: str
    blueprint: str | None
    controller_target: str
    model_code: str
    state: str
    device_count: int
    ramp_spec: dict[str, Any]
    auto_adopt: bool
    retired_at: str | None
    device_states: dict[str, int]
    created_at: str
    updated_at: str
