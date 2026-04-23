"""Inform key management — per-device AES key, rotated on controller demand."""

from __future__ import annotations

import os

# Well-known UniFi default key used by every device before adoption.
# Never log or expose this value; it is public knowledge but should not
# appear in production logs alongside real inform traffic.
DEFAULT_INFORM_KEY: bytes = bytes.fromhex("ba86f2bbe107c7c57eb5f2690775c712")


def generate_inform_key() -> bytes:
    """128-bit AES key for a new device."""
    return os.urandom(16)


def rotate_key(_current: bytes) -> bytes:
    """Controller-requested key rotation — a fresh key, independent of current."""
    return os.urandom(16)
