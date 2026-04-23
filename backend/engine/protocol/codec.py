"""High-level codec — combines TNBU framing, crypto, and zlib compression.

Inbound flow:  bytes -> decode TNBU -> decrypt -> decompress -> JSON
Outbound flow: JSON -> compress -> encrypt -> encode TNBU -> bytes
"""

from __future__ import annotations

import json
import os
import zlib
from typing import Any

from .crypto import decrypt_cbc, decrypt_gcm, encrypt_cbc, encrypt_gcm
from .tnbu import FLAG_AES_GCM, FLAG_COMPRESSED, FLAG_ENCRYPTED, InformFrame

_CBC_IV_LEN = 16
_GCM_NONCE_LEN = 12


def encode_inform(
    *,
    payload: dict[str, Any],
    key: bytes,
    mac: bytes,
    use_gcm: bool = True,
) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    flags = FLAG_ENCRYPTED
    compressed = zlib.compress(raw)
    # Only compress when it actually saves bytes.
    data = compressed if len(compressed) < len(raw) else raw
    if data is compressed:
        flags |= FLAG_COMPRESSED

    if use_gcm:
        nonce = os.urandom(_GCM_NONCE_LEN)
        ciphertext = encrypt_gcm(key, nonce, data)
        flags |= FLAG_AES_GCM
        frame = InformFrame(mac=mac, flags=flags, iv_or_nonce=nonce, payload=ciphertext)
    else:
        iv = os.urandom(_CBC_IV_LEN)
        ciphertext = encrypt_cbc(key, iv, data)
        frame = InformFrame(mac=mac, flags=flags, iv_or_nonce=iv, payload=ciphertext)

    return frame.encode()


def decode_inform(raw: bytes, *, key: bytes) -> dict[str, Any]:
    frame = InformFrame.decode(raw)

    data = frame.payload
    if frame.flags & FLAG_ENCRYPTED:
        if frame.flags & FLAG_AES_GCM:
            data = decrypt_gcm(key, frame.iv_or_nonce, data)
        else:
            data = decrypt_cbc(key, frame.iv_or_nonce, data)

    if frame.flags & FLAG_COMPRESSED:
        data = zlib.decompress(data)

    result: dict[str, Any] = json.loads(data)
    return result
