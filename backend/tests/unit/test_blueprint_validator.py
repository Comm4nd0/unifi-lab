"""Unit tests for apps.blueprints.validator and apps.blueprints.materialise."""

from __future__ import annotations

import pytest

from apps.blueprints.materialise import materialise
from apps.blueprints.validator import ValidationResult, parse_yaml, validate

# ── parse_yaml ────────────────────────────────────────────────────────────────


def test_parse_yaml_valid_returns_dict() -> None:
    src = "schema_version: uvl-blueprint/v1\nname: test\n"
    data, err = parse_yaml(src)
    assert data is not None
    assert err is None
    assert data["name"] == "test"


def test_parse_yaml_invalid_yaml_returns_error() -> None:
    data, err = parse_yaml("{ bad: yaml: here:")
    assert data is None
    assert err is not None
    assert "YAML" in err


def test_parse_yaml_non_dict_returns_error() -> None:
    data, err = parse_yaml("- item1\n- item2\n")
    assert data is None
    assert err is not None
    assert "mapping" in err.lower()


def test_parse_yaml_empty_string_returns_error() -> None:
    data, err = parse_yaml("")
    assert data is None
    assert err is not None


# ── validate — structural ─────────────────────────────────────────────────────

MINIMAL_VALID = {
    "schema_version": "uvl-blueprint/v1",
    "name": "test-lab",
    "site": {
        "networks": [{"name": "default", "vlan": 1, "subnet": "192.168.1.0/24"}],
        "devices": [{"hostname": "gw", "model": "UDR"}],
    },
}


@pytest.mark.django_db
def test_validate_minimal_valid_blueprint() -> None:
    result = validate(MINIMAL_VALID)
    assert result.valid
    assert not result.has_errors()


@pytest.mark.django_db
def test_validate_missing_required_field_fails() -> None:
    bad = {"site": {}}  # missing schema_version and name
    result = validate(bad)
    assert not result.valid
    assert result.has_errors()


@pytest.mark.django_db
def test_validate_wrong_schema_version_fails() -> None:
    bad = {**MINIMAL_VALID, "schema_version": "unknown/v99"}
    result = validate(bad)
    assert not result.valid


# ── validate — semantic: hostname uniqueness ──────────────────────────────────


@pytest.mark.django_db
def test_validate_duplicate_hostname_is_error() -> None:
    data = {
        "schema_version": "uvl-blueprint/v1",
        "name": "dup",
        "site": {
            "devices": [
                {"hostname": "gw", "model": "UDR"},
                {"hostname": "gw", "model": "USW24P250"},
            ]
        },
    }
    result = validate(data)
    assert not result.valid
    errors = [i for i in result.issues if i.severity == "error"]
    assert any("Duplicate hostname" in e.message for e in errors)


# ── validate — semantic: WLAN network cross-reference ────────────────────────


@pytest.mark.django_db
def test_validate_wlan_references_unknown_network() -> None:
    data = {
        "schema_version": "uvl-blueprint/v1",
        "name": "wlan-ref",
        "site": {
            "networks": [{"name": "default", "vlan": 1, "subnet": "10.0.0.0/24"}],
            "wlans": [{"ssid": "MyNet", "network": "no-such-network", "security": "wpa2", "passphrase": "secret12"}],
            "devices": [{"hostname": "ap", "model": "U6-Pro"}],
        },
    }
    result = validate(data)
    assert not result.valid
    assert any("unknown network" in i.message for i in result.issues if i.severity == "error")


# ── validate — semantic: uplink resolution ───────────────────────────────────


@pytest.mark.django_db
def test_validate_uplink_references_unknown_hostname() -> None:
    data = {
        "schema_version": "uvl-blueprint/v1",
        "name": "uplink-ref",
        "site": {
            "devices": [
                {"hostname": "ap", "model": "U6-Pro", "uplink": "nonexistent-switch"},
            ]
        },
    }
    result = validate(data)
    assert not result.valid
    assert any("unknown hostname" in i.message for i in result.issues if i.severity == "error")


# ── validate — semantic: unknown model is warning, not error ─────────────────


@pytest.mark.django_db
def test_validate_unknown_model_is_warning_not_error() -> None:
    data = {
        "schema_version": "uvl-blueprint/v1",
        "name": "model-warn",
        "site": {
            "devices": [{"hostname": "ap", "model": "NONEXISTENT-MODEL-XYZ"}]
        },
    }
    result = validate(data)
    # Structurally valid — model field passes JSON Schema (no enum constraint)
    # but semantic check warns about missing DeviceTemplate
    warnings = [i for i in result.issues if i.severity == "warning"]
    assert any("DeviceTemplate" in w.message or "template" in w.message.lower() for w in warnings)
    # No blocking errors from this alone
    errors = [i for i in result.issues if i.severity == "error"]
    assert not errors


# ── ValidationResult helpers ──────────────────────────────────────────────────


def test_validation_result_has_errors_true_on_error() -> None:
    r = ValidationResult(valid=False)
    r.add("error", "path", "something bad")
    assert r.has_errors()


def test_validation_result_has_errors_false_on_warning_only() -> None:
    r = ValidationResult(valid=True)
    r.add("warning", "path", "heads up")
    assert not r.has_errors()


# ── materialise ───────────────────────────────────────────────────────────────


def test_materialise_returns_one_spec_per_device() -> None:
    data = {
        "name": "home-lab",
        "site": {
            "devices": [
                {"hostname": "gw", "model": "UDR"},
                {"hostname": "sw", "model": "USW24P250", "uplink": "gw"},
                {"hostname": "ap", "model": "U6-Pro", "uplink": "sw", "network": "default"},
            ]
        },
    }
    specs = materialise(data)
    assert len(specs) == 3
    assert specs[0].hostname == "gw"
    assert specs[1].hostname == "sw"
    assert specs[2].hostname == "ap"


def test_materialise_mac_is_laa_unicast() -> None:
    data = {"name": "lab", "site": {"devices": [{"hostname": "ap", "model": "U6-Pro"}]}}
    specs = materialise(data)
    first = int(specs[0].mac_address.split(":")[0], 16)
    assert first & 0x02  # LAA bit
    assert not (first & 0x01)  # unicast


def test_materialise_mac_is_deterministic() -> None:
    data = {"name": "lab", "site": {"devices": [{"hostname": "ap", "model": "U6-Pro"}]}}
    a = materialise(data)
    b = materialise(data)
    assert a[0].mac_address == b[0].mac_address


def test_materialise_mac_differs_by_hostname() -> None:
    data = {
        "name": "lab",
        "site": {
            "devices": [
                {"hostname": "ap-1", "model": "U6-Pro"},
                {"hostname": "ap-2", "model": "U6-Pro"},
            ]
        },
    }
    specs = materialise(data)
    assert specs[0].mac_address != specs[1].mac_address


def test_materialise_preserves_network_and_uplink() -> None:
    data = {
        "name": "lab",
        "site": {
            "devices": [
                {"hostname": "ap", "model": "U6-Pro", "network": "iot", "uplink": "sw"},
            ]
        },
    }
    specs = materialise(data)
    assert specs[0].network == "iot"
    assert specs[0].uplink == "sw"


def test_materialise_empty_site_devices_returns_empty() -> None:
    data = {"name": "empty", "site": {"devices": []}}
    assert materialise(data) == []


def test_materialise_uses_blueprint_slug_param() -> None:
    data = {"name": "ignored", "site": {"devices": [{"hostname": "ap", "model": "U6-Pro"}]}}
    spec_a = materialise(data, blueprint_slug="slug-a")
    spec_b = materialise(data, blueprint_slug="slug-b")
    # Different slugs → different MACs for same hostname
    assert spec_a[0].mac_address != spec_b[0].mac_address
