"""UUIDv7 generator.

Python's stdlib doesn't ship UUIDv7 yet. This implementation follows the
IETF draft (time-ordered 128-bit identifier): 48-bit unix-millisecond
timestamp, 4-bit version, 12-bit random, 2-bit variant, 62-bit random.
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    value = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return uuid.UUID(int=value)
