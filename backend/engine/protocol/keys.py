"""Inform key management — per-device AES key, rotated on controller demand."""

from __future__ import annotations

import os


def generate_inform_key() -> bytes:
    """128-bit AES key for a new device."""
    return os.urandom(16)


def rotate_key(_current: bytes) -> bytes:
    """Controller-requested key rotation — a fresh key, independent of current."""
    return os.urandom(16)
