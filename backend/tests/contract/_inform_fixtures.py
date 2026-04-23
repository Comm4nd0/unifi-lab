"""Shared helpers for the inform codec test harness.

The harness discovers paired ``<name>.bin`` + ``<name>.meta.yaml`` files
under ``tests/fixtures/informs/`` and yields them as ``InformFixture``
records. Tests parametrize over the result so new captures pick up test
coverage automatically — just drop the pair into the fixtures directory
and re-run the suite.

Synthetic in-memory fixtures are also supported for harness self-tests;
see ``make_synthetic_fixture``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "informs"


@dataclass(frozen=True)
class InformFixture:
    """One paired capture used by the codec tests.

    ``raw`` is the exact TCP payload bytes we expect the codec to
    round-trip. ``meta`` is the parsed sidecar; schema is documented in
    the fixtures README.
    """

    name: str
    raw: bytes
    meta: dict[str, Any]

    @property
    def inform_key(self) -> bytes:
        hex_key = str(self.meta.get("inform_key", "")).replace(":", "")
        if not hex_key:
            raise ValueError(f"fixture {self.name} missing inform_key")
        return bytes.fromhex(hex_key)

    @property
    def expected_mac(self) -> bytes:
        raw = str(self.meta.get("expected_mac", "")).replace(":", "").replace("-", "")
        if len(raw) != 12:
            raise ValueError(f"fixture {self.name} expected_mac must be 6 bytes hex")
        return bytes.fromhex(raw)

    @property
    def expected_aes_variant(self) -> str:
        variant = str(self.meta.get("expected_aes_variant", "gcm")).lower()
        if variant not in ("cbc", "gcm"):
            raise ValueError(f"fixture {self.name} aes_variant must be cbc or gcm")
        return variant

    @property
    def expected_payload_keys(self) -> list[str]:
        keys = self.meta.get("expected_payload_keys") or []
        if not isinstance(keys, list):
            raise ValueError(f"fixture {self.name} expected_payload_keys must be a list")
        return [str(k) for k in keys]


def discover_fixtures(directory: Path = FIXTURES_DIR) -> list[InformFixture]:
    """Find every paired ``.bin`` + ``.meta.yaml`` under ``directory``.

    Returns an empty list when the directory is missing or empty so
    the harness can run cleanly on a fresh clone that has no captures
    yet. Unpaired files are silently ignored — they don't error the
    test run.
    """
    if not directory.exists():
        return []
    fixtures: list[InformFixture] = []
    for bin_path in sorted(directory.glob("*.bin")):
        meta_path = bin_path.with_suffix(".meta.yaml")
        if not meta_path.exists():
            continue
        raw = bin_path.read_bytes()
        meta = yaml.safe_load(meta_path.read_text()) or {}
        fixtures.append(InformFixture(name=bin_path.stem, raw=raw, meta=meta))
    return fixtures


def make_synthetic_fixture(
    *,
    name: str = "synthetic",
    raw: bytes = b"TNBU\x00\x00\x00\x01" + b"\x02\x00\x00\xaa\xbb\xcc" + b"\x00\x05",
    mac: str = "02:00:00:aa:bb:cc",
    key_hex: str = "00" * 16,
    aes_variant: str = "gcm",
    payload_keys: tuple[str, ...] = ("mac", "model", "version"),
) -> InformFixture:
    """Build an in-memory ``InformFixture`` for harness self-tests.

    The raw bytes are a well-formed TNBU header prefix — enough for the
    loader's shape assertions, not a valid full frame. Real captures
    always supersede this when present.
    """
    return InformFixture(
        name=name,
        raw=raw,
        meta={
            "name": name,
            "description": "synthetic self-test fixture",
            "inform_key": key_hex,
            "expected_mac": mac,
            "expected_aes_variant": aes_variant,
            "expected_payload_keys": list(payload_keys),
        },
    )
