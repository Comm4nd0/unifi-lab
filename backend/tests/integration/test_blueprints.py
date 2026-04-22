"""Blueprint CRUD + validation endpoint."""

from __future__ import annotations

import pytest

VALID_YAML = """
schema_version: uvl-blueprint/v1
name: example-home
description: Minimal home site
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
    - name: iot
      vlan: 10
      subnet: 192.168.10.0/24
  wlans:
    - ssid: CV-Home
      network: default
      security: wpa2
      passphrase: supersecret
  devices:
    - hostname: gateway
      model: UDR
    - hostname: switch-main
      model: USW24P250
      uplink: gateway
    - hostname: ap-office
      model: U6-Pro
      uplink: switch-main
      network: default
"""

DUPLICATE_HOSTNAME_YAML = """
schema_version: uvl-blueprint/v1
name: broken
site:
  devices:
    - hostname: gateway
      model: UDR
    - hostname: gateway
      model: U6-Pro
"""

BAD_SCHEMA_YAML = """
schema_version: uvl-blueprint/v1
name: missing-site
"""


@pytest.mark.django_db
def test_validate_accepts_valid_blueprint(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/validate/",
        {"source_yaml": VALID_YAML},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["valid"] is True
    errors = [i for i in resp.data["issues"] if i["severity"] == "error"]
    assert errors == []


@pytest.mark.django_db
def test_validate_reports_duplicate_hostnames(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/validate/",
        {"source_yaml": DUPLICATE_HOSTNAME_YAML},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["valid"] is False
    messages = " ".join(i["message"] for i in resp.data["issues"])
    assert "Duplicate hostname" in messages


@pytest.mark.django_db
def test_validate_reports_schema_violations(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/validate/",
        {"source_yaml": BAD_SCHEMA_YAML},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["valid"] is False
    messages = " ".join(i["message"] for i in resp.data["issues"])
    assert "site" in messages.lower()


@pytest.mark.django_db
def test_validate_reports_yaml_errors(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/validate/",
        {"source_yaml": "name: [unterminated"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["valid"] is False


@pytest.mark.django_db
def test_create_blueprint_parses_yaml_and_sets_version(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/",
        {"name": "ex", "source_yaml": VALID_YAML},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["version"] == 1
    assert resp.data["parsed_json"]["name"] == "example-home"


@pytest.mark.django_db
def test_update_increments_version(api_client):  # type: ignore[no-untyped-def]
    create = api_client.post(
        "/api/v1/blueprints/",
        {"name": "versioned", "source_yaml": VALID_YAML},
        format="json",
    )
    blueprint_id = create.data["id"]

    updated_yaml = VALID_YAML.replace("example-home", "example-home-v2")
    update = api_client.put(
        f"/api/v1/blueprints/{blueprint_id}/",
        {"name": "versioned", "source_yaml": updated_yaml},
        format="json",
    )
    assert update.status_code == 200, update.data
    assert update.data["version"] == 2
    assert update.data["parsed_json"]["name"] == "example-home-v2"


@pytest.mark.django_db
def test_create_rejects_invalid_blueprint(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/",
        {"name": "broken", "source_yaml": DUPLICATE_HOSTNAME_YAML},
        format="json",
    )
    assert resp.status_code == 400
    assert "source_yaml" in resp.data


@pytest.mark.django_db
def test_warning_when_model_code_unknown(api_client):  # type: ignore[no-untyped-def]
    exotic_yaml = """
schema_version: uvl-blueprint/v1
name: exotic
site:
  devices:
    - hostname: switch
      model: NOT-A-REAL-MODEL
"""
    # Ensure no templates exist for the exotic model
    from apps.templates.models import DeviceTemplate

    DeviceTemplate.objects.filter(model_code="NOT-A-REAL-MODEL").delete()

    resp = api_client.post(
        "/api/v1/blueprints/validate/",
        {"source_yaml": exotic_yaml},
        format="json",
    )
    # Warnings don't flip valid=False
    assert resp.data["valid"] is True
    warnings = [i for i in resp.data["issues"] if i["severity"] == "warning"]
    assert any("NOT-A-REAL-MODEL" in w["message"] for w in warnings)


@pytest.mark.django_db
def test_seed_blueprint_round_trips():  # type: ignore[no-untyped-def]
    """The example blueprint in the test corpus round-trips clean."""
    # Sanity: imports + validator run end-to-end.
    from apps.blueprints.validator import parse_yaml, validate

    parsed, err = parse_yaml(VALID_YAML)
    assert err is None
    assert parsed is not None
    # Models aren't seeded in every fixture path — validator just warns.
    result = validate(parsed)
    # Structural errors should be zero; warnings may exist.
    assert not result.has_errors()
    assert result.parsed is not None
    assert result.parsed["site"]["devices"][0]["hostname"] == "gateway"
