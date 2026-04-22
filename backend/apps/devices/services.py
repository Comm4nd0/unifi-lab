"""Domain services for virtual devices.

Keeps views thin and business logic testable. Services do not hit the
inform protocol — that's the worker's job. Services orchestrate DB state
and emit events the worker picks up.
"""

from __future__ import annotations

import secrets

from .models import VirtualDevice


def generate_mac() -> str:
    """Locally-administered unicast MAC in the 02:00:00:XX:XX:XX space."""
    b = [0x02, 0x00, 0x00, *secrets.token_bytes(3)]
    return ":".join(f"{x:02x}" for x in b)


def generate_serial(model_code: str) -> str:
    return f"{model_code}-{secrets.token_hex(6).upper()}"


def create_device(
    *,
    model_code: str,
    firmware_version: str = "",
    controller_target_id: str | None = None,
    fleet_id: str | None = None,
) -> VirtualDevice:
    return VirtualDevice.objects.create(
        mac_address=generate_mac(),
        serial_number=generate_serial(model_code),
        model_code=model_code,
        firmware_version=firmware_version,
        controller_target_id=controller_target_id,
        fleet_id=fleet_id,
    )
