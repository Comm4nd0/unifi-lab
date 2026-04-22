"""Ramp-spec interpreter.

Given a ``ramp_spec`` dict and a list of device ids, produces a per-device
delay (ms) so the supervisor can stagger spawns. Pure function — easy to
unit test.

Supported modes (see ``Components/23 - Fleet Manager``):

- ``all-at-once`` — default; every delay is 0.
- ``linear`` — ``devices_per_sec`` steady spawn rate.
- ``staged`` — explicit stages with ``count`` + ``after_ms``.
- ``random`` — ``jitter_ms: [low, high]`` uniform random delays.

Unknown modes fall back to ``all-at-once`` rather than raising —
fleet creation shouldn't 500 on a bad spec.
"""

from __future__ import annotations

import random
from typing import Any


def compute_delays(device_count: int, ramp_spec: dict[str, Any] | None) -> list[int]:
    spec = ramp_spec or {}
    mode = spec.get("mode", "all-at-once")

    if device_count <= 0:
        return []

    if mode == "linear":
        raw_rate = spec.get("devices_per_sec", 1)
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            rate = 1.0
        if rate <= 0:
            return [0] * device_count
        step_ms = 1000.0 / rate
        return [int(i * step_ms) for i in range(device_count)]

    if mode == "staged":
        delays: list[int] = []
        idx = 0
        for stage in spec.get("stages", []):
            count = int(stage.get("count", 0))
            after = int(stage.get("after_ms", 0))
            for _ in range(count):
                if idx >= device_count:
                    break
                delays.append(after)
                idx += 1
        while idx < device_count:
            delays.append(0)
            idx += 1
        return delays

    if mode == "random":
        jitter = spec.get("jitter_ms", [0, 0])
        if isinstance(jitter, list) and len(jitter) >= 2:
            low, high = int(jitter[0]), int(jitter[1])
        else:
            low = high = int(jitter[0]) if jitter else 0
        if low > high:
            low, high = high, low
        rng = random.Random(spec.get("seed"))
        return [rng.randint(low, high) for _ in range(device_count)]

    return [0] * device_count


def ramp_duration_ms(delays: list[int]) -> int:
    """Total ramp duration — the max delay + a small settle buffer."""
    return (max(delays) if delays else 0) + 500
