"""Inform-codec test harness — loader + sidecar contract.

Exercises the fixture loader itself so that the surrounding codec tests
can rely on it. These run clean on a fresh clone with no real captures;
the parametrized codec assertions live in ``test_codec.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ._inform_fixtures import (
    InformFixture,
    discover_fixtures,
    make_synthetic_fixture,
)


def test_discover_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert discover_fixtures(missing) == []


def test_discover_returns_empty_when_dir_empty(tmp_path: Path) -> None:
    assert discover_fixtures(tmp_path) == []


def test_discover_ignores_unpaired_bin_without_meta(tmp_path: Path) -> None:
    (tmp_path / "orphan.bin").write_bytes(b"TNBU")
    assert discover_fixtures(tmp_path) == []


def test_discover_loads_paired_bin_and_meta(tmp_path: Path) -> None:
    (tmp_path / "one.bin").write_bytes(b"TNBU\x00\x00\x00\x01payload")
    (tmp_path / "one.meta.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "one",
                "inform_key": "aa" * 16,
                "expected_mac": "02:00:00:aa:bb:cc",
                "expected_aes_variant": "gcm",
                "expected_payload_keys": ["mac", "model"],
            }
        )
    )
    fixtures = discover_fixtures(tmp_path)
    assert len(fixtures) == 1
    f = fixtures[0]
    assert f.name == "one"
    assert f.raw.startswith(b"TNBU")
    assert f.inform_key == bytes.fromhex("aa" * 16)
    assert f.expected_mac == bytes.fromhex("020000aabbcc")
    assert f.expected_aes_variant == "gcm"
    assert f.expected_payload_keys == ["mac", "model"]


def test_synthetic_fixture_round_trip_has_sane_defaults() -> None:
    f = make_synthetic_fixture()
    assert isinstance(f, InformFixture)
    assert f.raw.startswith(b"TNBU")
    assert f.expected_mac == bytes.fromhex("020000aabbcc")
    assert f.inform_key == bytes.fromhex("00" * 16)
    assert f.expected_aes_variant == "gcm"


def test_fixture_rejects_malformed_mac() -> None:
    f = make_synthetic_fixture()
    bad = InformFixture(name="bad", raw=f.raw, meta={**f.meta, "expected_mac": "bogus"})
    with pytest.raises(ValueError, match="expected_mac"):
        _ = bad.expected_mac


def test_fixture_rejects_missing_inform_key() -> None:
    f = make_synthetic_fixture()
    bad = InformFixture(name="bad", raw=f.raw, meta={**f.meta, "inform_key": ""})
    with pytest.raises(ValueError, match="inform_key"):
        _ = bad.inform_key


def test_fixture_rejects_unknown_aes_variant() -> None:
    f = make_synthetic_fixture()
    bad = InformFixture(
        name="bad",
        raw=f.raw,
        meta={**f.meta, "expected_aes_variant": "chacha"},
    )
    with pytest.raises(ValueError, match="aes_variant"):
        _ = bad.expected_aes_variant
