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

Phase 0: codec is a stub. Real implementation in Phase 0 tail.
"""

from __future__ import annotations

from dataclasses import dataclass

MAGIC = b"TNBU"
VERSION = 1
FLAG_ENCRYPTED = 1 << 0
FLAG_COMPRESSED = 1 << 1
FLAG_AES_GCM = 1 << 2


@dataclass
class InformFrame:
    mac: bytes  # 6 bytes
    flags: int
    iv_or_nonce: bytes
    payload: bytes  # encrypted + optionally compressed

    def encode(self) -> bytes:
        raise NotImplementedError("TNBU encode not implemented — awaiting pcap captures")

    @classmethod
    def decode(cls, raw: bytes) -> InformFrame:
        raise NotImplementedError("TNBU decode not implemented — awaiting pcap captures")
