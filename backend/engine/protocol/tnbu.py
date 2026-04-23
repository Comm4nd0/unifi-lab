"""TNBU framing.

Wire format (from reverse-engineering work in jeffreykog/unifi-inform-protocol):

    Offset  Size  Field
    ------  ----  -----
    0       4     Magic ("TNBU")
    4       4     Packet version (currently 1)
    8       6     Device MAC (binary)
    14      2     Flags (bit0=encrypted, bit1=zlib compressed, bit2=AES-GCM)
    16      4     IV length (for AES-CBC) or nonce length (for AES-GCM)
    20      N     IV / nonce bytes
    20+N    4     Payload data length
    24+N    M     Payload (encrypted + optionally compressed)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"TNBU"
VERSION = 1
FLAG_ENCRYPTED = 1 << 0
FLAG_COMPRESSED = 1 << 1
FLAG_AES_GCM = 1 << 2

# ">4sI6sHI" = magic(4) + version(4) + mac(6) + flags(2) + iv_len(4) = 20 bytes
_HEADER_FMT = ">4sI6sHI"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 20


@dataclass
class InformFrame:
    mac: bytes  # 6 bytes
    flags: int
    iv_or_nonce: bytes
    payload: bytes  # encrypted + optionally compressed

    def encode(self) -> bytes:
        header = struct.pack(
            _HEADER_FMT,
            MAGIC,
            VERSION,
            self.mac,
            self.flags,
            len(self.iv_or_nonce),
        )
        return header + self.iv_or_nonce + struct.pack(">I", len(self.payload)) + self.payload

    @classmethod
    def decode(cls, raw: bytes) -> InformFrame:
        if len(raw) < _HEADER_SIZE:
            raise ValueError(f"Frame too short: {len(raw)} < {_HEADER_SIZE}")
        magic, version, mac, flags, iv_len = struct.unpack_from(_HEADER_FMT, raw, 0)
        if magic != MAGIC:
            raise ValueError(f"Bad magic: {magic!r}")
        if version != VERSION:
            raise ValueError(f"Unsupported TNBU version: {version}")
        offset = _HEADER_SIZE
        if len(raw) < offset + iv_len + 4:
            raise ValueError("Frame truncated in IV/nonce region")
        iv = raw[offset : offset + iv_len]
        offset += iv_len
        (payload_len,) = struct.unpack_from(">I", raw, offset)
        offset += 4
        payload = raw[offset : offset + payload_len]
        if len(payload) < payload_len:
            raise ValueError(f"Payload truncated: {len(payload)} < {payload_len}")
        return cls(mac=mac, flags=flags, iv_or_nonce=iv, payload=payload)
