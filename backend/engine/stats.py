"""Stats reporter — aggregates per-device counters and emits them in inform payloads."""

from __future__ import annotations


def zero_stats() -> dict[str, int]:
    return {"bytes_rx": 0, "bytes_tx": 0, "pkts_rx": 0, "pkts_tx": 0, "uptime_s": 0}
