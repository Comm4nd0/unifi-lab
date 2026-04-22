"""High-level codec — combines TNBU framing, crypto, and zlib compression.

Inbound flow:  bytes -> decode TNBU -> decrypt -> decompress -> JSON
Outbound flow: JSON -> compress -> encrypt -> encode TNBU -> bytes
"""

from __future__ import annotations

from typing import Any


def encode_inform(
    *,
    payload: dict[str, Any],
    key: bytes,
    mac: bytes,
    use_gcm: bool = True,
) -> bytes:
    raise NotImplementedError("inform encode not implemented — awaiting pcap captures")


def decode_inform(raw: bytes, *, key: bytes) -> dict[str, Any]:
    raise NotImplementedError("inform decode not implemented — awaiting pcap captures")
