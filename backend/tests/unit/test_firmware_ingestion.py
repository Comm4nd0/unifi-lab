"""Unit tests for firmware ingestion pipeline helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.firmware.tasks import (
    _binwalk_offsets,
    _extract_caps,
    _guess_family,
    _identify_from_filename,
    _identify_from_fs,
)

# ── _guess_family ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code,expected",
    [
        ("U6-Pro", "ap"),
        ("U6-LITE", "ap"),
        ("U7-Pro-Max", "ap"),
        ("UAP-AC-Pro", "ap"),
        ("USW24P250", "switch"),
        ("US-24-250W", "switch"),
        ("UDM", "gateway"),
        ("UDR", "gateway"),
        ("USG-PRO-4", "gateway"),
        ("UCG-Ultra", "gateway"),
        ("UNKNOWN-XYZ", "other"),
    ],
)
def test_guess_family(code: str, expected: str) -> None:
    assert _guess_family(code) == expected


# ── _identify_from_filename ───────────────────────────────────────────────────


def test_identify_from_filename_typical() -> None:
    codes, version = _identify_from_filename("U6-Lite-6.6.58.14777.bin")
    assert codes == ["U6-LITE"]
    assert version == "6.6.58.14777"


def test_identify_from_filename_switch() -> None:
    codes, version = _identify_from_filename("USW24P250-8.3.42.bin")
    assert codes == ["USW24P250"]
    assert version == "8.3.42"


def test_identify_from_filename_no_match_returns_empty() -> None:
    codes, version = _identify_from_filename("garbage.bin")
    assert codes == []
    assert version == ""


def test_identify_from_filename_with_firmware_infix() -> None:
    codes, version = _identify_from_filename("UAP-AC-Lite-firmware-5.43.36.bin")
    assert len(codes) == 1
    assert "5.43.36" in version


# ── _identify_from_fs ─────────────────────────────────────────────────────────


def test_identify_from_fs_reads_board_info(tmp_path: Path) -> None:
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "board.info").write_text("board.shortname=U6-Lite\nboard.name=UniFi 6 Lite\n")
    usr_lib = tmp_path / "usr" / "lib"
    usr_lib.mkdir(parents=True)
    (usr_lib / "version").write_text("6.6.58.14777\n")

    codes, version = _identify_from_fs(tmp_path, "dummy.bin")
    assert codes == ["U6-Lite"]
    assert "6.6.58" in version


def test_identify_from_fs_falls_back_to_filename(tmp_path: Path) -> None:
    # No board.info at all — should fall back to filename heuristic
    codes, version = _identify_from_fs(tmp_path, "USW24P250-8.3.42.bin")
    assert codes == ["USW24P250"]
    assert version == "8.3.42"


def test_identify_from_fs_version_from_file_preferred(tmp_path: Path) -> None:
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "board.info").write_text("board.shortname=UDM\n")
    usr_lib = tmp_path / "usr" / "lib"
    usr_lib.mkdir(parents=True)
    (usr_lib / "version").write_text("3.2.7.9018\n")

    codes, version = _identify_from_fs(tmp_path, "UDM-2.0.0.bin")
    assert codes == ["UDM"]
    assert "3.2.7" in version  # from version file, not filename


# ── _extract_caps ─────────────────────────────────────────────────────────────


def test_extract_caps_reads_port_and_radio(tmp_path: Path) -> None:
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "board.info").write_text("port.count=24\nradio.count=2\nother=ignored\n")

    caps = _extract_caps(tmp_path)
    assert caps == {"port_count": 24, "radio_count": 2}


def test_extract_caps_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _extract_caps(tmp_path) == {}


def test_extract_caps_partial_info(tmp_path: Path) -> None:
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "board.info").write_text("port.count=8\n")

    caps = _extract_caps(tmp_path)
    assert caps == {"port_count": 8}
    assert "radio_count" not in caps


# ── _binwalk_offsets ──────────────────────────────────────────────────────────


def test_binwalk_offsets_parses_squashfs_lines(tmp_path: Path) -> None:
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"\x00" * 100)

    mock_result = MagicMock()
    mock_result.stdout = (
        "DECIMAL       HEXADECIMAL     DESCRIPTION\n"
        "0             0x0             uImage header\n"
        "1245184       0x130000        Squashfs filesystem, little endian\n"
        "2097152       0x200000        Another squashfs filesystem\n"
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        offsets = _binwalk_offsets(fw)

    mock_run.assert_called_once()
    assert offsets == [1245184, 2097152]


def test_binwalk_offsets_returns_empty_when_not_installed(tmp_path: Path) -> None:
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"\x00" * 10)

    with patch("subprocess.run", side_effect=FileNotFoundError("binwalk not found")):
        offsets = _binwalk_offsets(fw)

    assert offsets == []


def test_binwalk_offsets_returns_empty_on_timeout(tmp_path: Path) -> None:
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"\x00" * 10)

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("binwalk", 120)):
        offsets = _binwalk_offsets(fw)

    assert offsets == []


def test_binwalk_offsets_no_squashfs_in_output(tmp_path: Path) -> None:
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"\x00" * 10)

    mock_result = MagicMock()
    mock_result.stdout = "0    0x0    uImage\n512  0x200  LZMA compressed\n"

    with patch("subprocess.run", return_value=mock_result):
        offsets = _binwalk_offsets(fw)

    assert offsets == []
