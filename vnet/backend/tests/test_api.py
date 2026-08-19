"""API contract tests: the console talks to these endpoints."""

import pytest
from rest_framework.test import APIClient

from netsim.models import Device, Link, Port, Site
from netsim.seed import seed_demo_site


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def site(db) -> Site:
    return Site.objects.create(name="Test Site")


def _add(api: APIClient, site: Site, model: str) -> dict:
    """Add a catalogue device to a site and return the serialised response."""
    response = api.post(
        "/api/devices/", {"site": site.pk, "model": model}, format="json"
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_catalog_lists_every_model_with_ports(api):
    response = api.get("/api/catalog/")
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) >= 40
    switch = next(m for m in body["models"] if m["key"] == "usw-pro-24-poe")
    assert len(switch["ports"]) == 26
    assert switch["poe_budget_w"] == 400
    assert "cat6" in body["cables"]


def test_catalog_filters_by_line(api):
    response = api.get("/api/catalog/?line=ap")
    assert {m["line"] for m in response.json()["models"]} == {"ap"}


def test_adding_a_device_materialises_its_ports(api, site):
    response = api.post(
        "/api/devices/",
        {"site": site.pk, "model": "usw-pro-24-poe", "name": "Core", "x": 10, "y": 20},
        format="json",
    )
    assert response.status_code == 201, response.json()
    device = Device.objects.get(pk=response.json()["id"])
    assert device.ports.count() == 26
    assert device.mac and device.ip
    assert response.json()["ports"][0]["label"] == "Port 1"


def test_unknown_model_is_rejected(api, site):
    response = api.post(
        "/api/devices/", {"site": site.pk, "model": "usw-imaginary"}, format="json"
    )
    assert response.status_code == 400
    assert "catalogue" in str(response.json()).lower()


def test_patching_two_ports_creates_a_link(api, site):
    a = _add(api, site, "usw-24-poe")
    b = _add(api, site, "u7-pro")
    a_port = Port.objects.get(device_id=a["id"], index=2)
    b_port = Port.objects.get(device_id=b["id"], index=1)
    response = api.post(
        "/api/links/",
        {"site": site.pk, "a_port": a_port.pk, "b_port": b_port.pk, "cable": "cat6"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert Link.objects.count() == 1


def test_a_port_can_only_be_patched_once(api, site):
    a = _add(api, site, "usw-24-poe")
    b = _add(api, site, "u7-pro")
    c = _add(api, site, "u6-lite")
    a_port = Port.objects.get(device_id=a["id"], index=2)
    payload = {"site": site.pk, "a_port": a_port.pk, "cable": "cat6"}
    first = api.post(
        "/api/links/",
        {**payload, "b_port": Port.objects.get(device_id=b["id"], index=1).pk},
        format="json",
    )
    assert first.status_code == 201
    second = api.post(
        "/api/links/",
        {**payload, "b_port": Port.objects.get(device_id=c["id"], index=1).pk},
        format="json",
    )
    assert second.status_code == 400


def test_copper_cannot_be_patched_to_fibre(api, site):
    a = _add(api, site, "usw-pro-24-poe")
    b = _add(api, site, "u7-pro")
    response = api.post(
        "/api/links/",
        {
            "site": site.pk,
            "a_port": Port.objects.get(device_id=a["id"], index=25).pk,  # SFP+
            "b_port": Port.objects.get(device_id=b["id"], index=1).pk,  # RJ45
            "cable": "cat6",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "SFP+" in str(response.json())


def test_available_ports_excludes_patched_ones(api, site):
    a = _add(api, site, "usw-24-poe")
    b = _add(api, site, "u7-pro")
    api.post(
        "/api/links/",
        {
            "site": site.pk,
            "a_port": Port.objects.get(device_id=a["id"], index=2).pk,
            "b_port": Port.objects.get(device_id=b["id"], index=1).pk,
        },
        format="json",
    )
    free = api.get(f"/api/sites/{site.pk}/available-ports/?device={a['id']}").json()
    assert len(free) == 25
    assert all(p["index"] != 2 for p in free)


def test_simulation_endpoint_returns_the_console_payload(api, db):
    site = seed_demo_site("Sim Site")
    response = api.get(f"/api/sites/{site.pk}/simulation/")
    assert response.status_code == 200
    body = response.json()
    expected = {"health", "devices", "links", "clients", "stp", "power", "traffic", "issues"}
    assert expected <= set(body)
    assert len(body["devices"]) == 5
    assert body["health"]["device_count"] == 5
    # The seed deliberately includes a redundant run, so RSTP must block one port.
    assert len(body["stp"]["blocked_link_ids"]) == 1
    assert any(i["code"] == "stp.port_blocked" for i in body["issues"])
    gateway = next(d for d in body["devices"] if d["line"] == "gateway")
    assert gateway["stp"]["is_root"] is True


def test_position_endpoint_moves_a_device(api, site):
    device = _add(api, site, "u6-lite")
    response = api.post(
        f"/api/devices/{device['id']}/position/", {"x": 5, "y": -9}, format="json"
    )
    assert response.status_code == 200
    assert Device.objects.get(pk=device["id"]).x == 5


def test_port_configuration_can_be_changed(api, db):
    site = seed_demo_site("Port Site")
    port = Port.objects.filter(device__site=site, index=17).first()
    response = api.patch(
        f"/api/ports/{port.pk}/", {"poe_enabled": False, "name": "Reception"}, format="json"
    )
    assert response.status_code == 200
    port.refresh_from_db()
    assert port.poe_enabled is False
    assert port.label == "Reception"


def test_blueprint_round_trip(api, db):
    site = seed_demo_site("Blueprint Site")
    blueprint = api.get(f"/api/sites/{site.pk}/blueprint/").json()
    assert len(blueprint["devices"]) == 5
    assert len(blueprint["links"]) == 5

    response = api.post(
        f"/api/sites/{site.pk}/blueprint/",
        {"blueprint": blueprint, "name": "Copy"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    copy = Site.objects.get(pk=response.json()["id"])
    assert copy.devices.count() == 5
    assert copy.links.count() == 5
    assert copy.clients.count() == 4
    assert copy.flows.count() == 2
    # Flow endpoints must survive the round trip, not silently fall back to internet.
    assert set(copy.flows.values_list("src_client__name", flat=True)) == {"Workshop NAS"}

    original = api.get(f"/api/sites/{site.pk}/simulation/?t=0").json()
    duplicate = api.get(f"/api/sites/{copy.pk}/simulation/?t=0").json()
    assert original["health"]["counts"] == duplicate["health"]["counts"]


def test_blueprint_exports_as_yaml(api, db):
    site = seed_demo_site("Yaml Site")
    response = api.get(f"/api/sites/{site.pk}/blueprint/?as=yaml")
    assert response.status_code == 200
    assert b"devices:" in response.content


def test_seed_demo_endpoint(api, db):
    response = api.post("/api/sites/seed-demo/", {"name": "From API"}, format="json")
    assert response.status_code == 201
    assert Site.objects.filter(name="From API").exists()
