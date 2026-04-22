"""Unit tests for the ramp-spec interpreter."""

from __future__ import annotations

import pytest

from apps.fleets.ramp import compute_delays, ramp_duration_ms


def test_all_at_once_is_default_and_zero_delays():
    assert compute_delays(5, None) == [0, 0, 0, 0, 0]
    assert compute_delays(5, {}) == [0, 0, 0, 0, 0]
    assert compute_delays(5, {"mode": "all-at-once"}) == [0, 0, 0, 0, 0]


def test_zero_devices_returns_empty():
    assert compute_delays(0, {"mode": "linear", "devices_per_sec": 10}) == []


def test_linear_spreads_delays_by_rate():
    delays = compute_delays(5, {"mode": "linear", "devices_per_sec": 2})
    # 2/sec => 500ms between each
    assert delays == [0, 500, 1000, 1500, 2000]


def test_linear_fractional_rate_rounds_to_int_ms():
    delays = compute_delays(3, {"mode": "linear", "devices_per_sec": 3})
    # 1000/3 ≈ 333.33ms -> ints
    assert delays == [0, 333, 666]


def test_linear_zero_rate_falls_back_to_all_at_once():
    assert compute_delays(3, {"mode": "linear", "devices_per_sec": 0}) == [0, 0, 0]


def test_staged_assigns_per_stage_delays():
    spec = {
        "mode": "staged",
        "stages": [
            {"count": 2, "after_ms": 0},
            {"count": 3, "after_ms": 10_000},
        ],
    }
    assert compute_delays(5, spec) == [0, 0, 10_000, 10_000, 10_000]


def test_staged_pads_with_zero_when_stages_underfill():
    spec = {"mode": "staged", "stages": [{"count": 1, "after_ms": 500}]}
    assert compute_delays(3, spec) == [500, 0, 0]


def test_random_uses_seed_for_determinism():
    spec = {"mode": "random", "jitter_ms": [0, 1000], "seed": 42}
    first = compute_delays(5, spec)
    again = compute_delays(5, spec)
    assert first == again
    assert all(0 <= d <= 1000 for d in first)


def test_random_swaps_inverted_bounds():
    spec = {"mode": "random", "jitter_ms": [500, 100], "seed": 1}
    assert all(100 <= d <= 500 for d in compute_delays(10, spec))


def test_unknown_mode_falls_back_to_zero():
    assert compute_delays(3, {"mode": "novel-thing"}) == [0, 0, 0]


@pytest.mark.parametrize(
    "delays,expected",
    [
        ([0, 500, 1000], 1500),  # max + 500ms settle
        ([], 500),
        ([2000], 2500),
    ],
)
def test_ramp_duration_adds_settle_buffer(delays: list[int], expected: int):
    assert ramp_duration_ms(delays) == expected
