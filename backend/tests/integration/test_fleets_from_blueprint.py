"""Blueprint-driven fleet instantiation."""

from __future__ import annotations

import pytest

from apps.blueprints.models import Blueprint
from apps.devices.models import VirtualDevice
from apps.devices.services import deterministic_mac

BLUEPRINT_YAML = """
schema_version: uvl-blueprint/v1
name: bp-driven
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
  devices:
    - hostname: gateway
      model: UDR
    - hostname: switch-01
      model: USW24P250
      uplink: gateway
    - hostname: ap-01
      model: U6-Pro
      uplink: switch-01
      mac: 02:00:00:aa:bb:cc
"""


@pytest.fixture
def saved_blueprint(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/blueprints/",
        {"name": "bp-driven", "source_yaml": BLUEPRINT_YAML},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    return Blueprint.objects.get(pk=resp.data["id"])


@pytest.mark.django_db
def test_create_fleet_from_blueprint_spawns_devices_from_spec(
    api_client, controller_target, saved_blueprint
):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "bp-fleet",
            "controller_target": str(controller_target.id),
            "blueprint": str(saved_blueprint.id),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    fleet_id = resp.data["id"]
    assert resp.data["device_count"] == 3

    devices = VirtualDevice.objects.filter(fleet_id=fleet_id).order_by("hostname")
    hostnames = [d.hostname for d in devices]
    assert sorted(hostnames) == ["ap-01", "gateway", "switch-01"]

    models = {d.hostname: d.model_code for d in devices}
    assert models == {"gateway": "UDR", "switch-01": "USW24P250", "ap-01": "U6-Pro"}


@pytest.mark.django_db
def test_blueprint_fleet_honours_explicit_mac(api_client, controller_target, saved_blueprint):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "mac-honour",
            "controller_target": str(controller_target.id),
            "blueprint": str(saved_blueprint.id),
        },
        format="json",
    )
    fleet_id = resp.data["id"]
    ap = VirtualDevice.objects.get(fleet_id=fleet_id, hostname="ap-01")
    assert ap.mac_address == "02:00:00:aa:bb:cc"


@pytest.mark.django_db
def test_blueprint_fleet_generates_deterministic_mac(
    api_client, controller_target, saved_blueprint
):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "det-mac",
            "controller_target": str(controller_target.id),
            "blueprint": str(saved_blueprint.id),
        },
        format="json",
    )
    fleet_id = resp.data["id"]
    gw = VirtualDevice.objects.get(fleet_id=fleet_id, hostname="gateway")
    expected = deterministic_mac(blueprint_slug="bp-driven", hostname="gateway")
    assert gw.mac_address == expected


@pytest.mark.django_db
def test_simple_fleet_still_works_without_blueprint(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "simple",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 2,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert VirtualDevice.objects.filter(fleet_id=resp.data["id"]).count() == 2


@pytest.mark.django_db
def test_fleet_requires_blueprint_or_model_count(api_client, controller_target):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "neither",
            "controller_target": str(controller_target.id),
        },
        format="json",
    )
    assert resp.status_code == 400, resp.data
