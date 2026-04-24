"""Unit tests for device MAC / serial generation helpers."""

from __future__ import annotations

from apps.devices.services import deterministic_mac, generate_mac, generate_serial


# ── generate_mac ──────────────────────────────────────────────────────────────


def test_generate_mac_format() -> None:
    mac = generate_mac()
    parts = mac.split(":")
    assert len(parts) == 6
    assert all(len(p) == 2 for p in parts)
    assert all(int(p, 16) == int(p, 16) for p in parts)  # valid hex


def test_generate_mac_is_laa_unicast() -> None:
    mac = generate_mac()
    first_byte = int(mac.split(":")[0], 16)
    assert first_byte & 0x02  # locally administered bit set
    assert not (first_byte & 0x01)  # unicast (not multicast)


def test_generate_mac_prefix() -> None:
    mac = generate_mac()
    assert mac.startswith("02:00:00:")


def test_generate_mac_is_random() -> None:
    macs = {generate_mac() for _ in range(100)}
    assert len(macs) > 95  # extremely unlikely to get >5 collisions


# ── deterministic_mac ─────────────────────────────────────────────────────────


def test_deterministic_mac_is_stable() -> None:
    mac1 = deterministic_mac(blueprint_slug="home-lab", hostname="ap-office")
    mac2 = deterministic_mac(blueprint_slug="home-lab", hostname="ap-office")
    assert mac1 == mac2


def test_deterministic_mac_differs_by_hostname() -> None:
    mac1 = deterministic_mac(blueprint_slug="home-lab", hostname="ap-office")
    mac2 = deterministic_mac(blueprint_slug="home-lab", hostname="ap-lounge")
    assert mac1 != mac2


def test_deterministic_mac_differs_by_blueprint() -> None:
    mac1 = deterministic_mac(blueprint_slug="home-lab", hostname="ap-office")
    mac2 = deterministic_mac(blueprint_slug="office-lab", hostname="ap-office")
    assert mac1 != mac2


def test_deterministic_mac_is_laa_unicast() -> None:
    mac = deterministic_mac(blueprint_slug="slug", hostname="host")
    first_byte = int(mac.split(":")[0], 16)
    assert first_byte & 0x02
    assert not (first_byte & 0x01)


def test_deterministic_mac_prefix() -> None:
    mac = deterministic_mac(blueprint_slug="x", hostname="y")
    assert mac.startswith("02:00:00:")


# ── generate_serial ───────────────────────────────────────────────────────────


def test_generate_serial_format() -> None:
    serial = generate_serial("U6-Pro")
    assert serial.startswith("U6-Pro-")
    suffix = serial[len("U6-Pro-"):]
    assert len(suffix) == 12  # 6 bytes hex = 12 chars
    assert suffix == suffix.upper()


def test_generate_serial_is_random() -> None:
    serials = {generate_serial("UAP") for _ in range(50)}
    assert len(serials) > 45
