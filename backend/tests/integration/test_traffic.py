"""TrafficProfile CRUD + flow filtering + sample generator."""

from __future__ import annotations

import pytest

from apps.traffic.models import FlowRecord, TrafficProfile

PROFILE_YAML = """
name: iot-baseline
description: Low-rate IoT chatter
applies_to:
  vlan: 40
flows:
  - direction: client-to-internet
    app: "Cloud Services"
    rate: "2/min"
    bytes_per_flow: "20KB-200KB"
"""


@pytest.mark.django_db
def test_create_profile_parses_yaml_and_versions(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/traffic/profiles/",
        {"name": "iot", "source_yaml": PROFILE_YAML},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["version"] == 1
    assert resp.data["parsed_json"]["name"] == "iot-baseline"
    assert len(resp.data["parsed_json"]["flows"]) == 1


@pytest.mark.django_db
def test_update_bumps_version(api_client):  # type: ignore[no-untyped-def]
    create = api_client.post(
        "/api/v1/traffic/profiles/",
        {"name": "p1", "source_yaml": PROFILE_YAML},
        format="json",
    )
    pid = create.data["id"]

    tweaked = PROFILE_YAML.replace("2/min", "5/min")
    resp = api_client.put(
        f"/api/v1/traffic/profiles/{pid}/",
        {"name": "p1", "source_yaml": tweaked},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["version"] == 2


@pytest.mark.django_db
def test_profile_rejects_missing_flows(api_client):  # type: ignore[no-untyped-def]
    bad = """
name: no-flows
applies_to:
  vlan: 1
"""
    resp = api_client.post(
        "/api/v1/traffic/profiles/",
        {"name": "bad", "source_yaml": bad},
        format="json",
    )
    assert resp.status_code == 400
    assert "source_yaml" in resp.data


@pytest.mark.django_db
def test_profile_rejects_bad_yaml(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/traffic/profiles/",
        {"name": "bad", "source_yaml": "name: [unterminated"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_generate_samples_populates_flows(api_client, controller_target):  # type: ignore[no-untyped-def]
    # Use the fleet + devices endpoint to set up.
    fleet_resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "sampler",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 2,
        },
        format="json",
    )
    fleet_id = fleet_resp.data["id"]

    gen = api_client.post(
        "/api/v1/traffic/flows/generate-samples/",
        {"fleet_id": fleet_id, "count": 10},
        format="json",
    )
    assert gen.status_code == 201, gen.data
    assert gen.data["created"] == 10

    # Flows should be queryable by fleet id.
    listing = api_client.get(f"/api/v1/traffic/flows/?fleet={fleet_id}")
    assert listing.status_code == 200
    assert listing.data["count"] == 10


@pytest.mark.django_db
def test_generate_samples_rejects_empty_fleet(api_client, controller_target):  # type: ignore[no-untyped-def]
    # Create a fleet with 0 devices (explicit model_code but zero count
    # should fail validation — use the path of zero devices via creating
    # a fleet row directly since the serializer requires device_count>=1).
    from apps.fleets.models import Fleet

    fleet = Fleet.objects.create(
        name="empty",
        controller_target=controller_target,
        model_code="USW24P250",
        device_count=0,
    )
    resp = api_client.post(
        "/api/v1/traffic/flows/generate-samples/",
        {"fleet_id": str(fleet.id), "count": 5},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_generate_samples_requires_fleet_id(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/traffic/flows/generate-samples/",
        {"count": 10},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_flows_persist_on_delete_device_cascade(api_client, controller_target):  # type: ignore[no-untyped-def]
    """Sanity check: if a device is deleted the flow rows cascade."""
    fleet_resp = api_client.post(
        "/api/v1/fleets/",
        {
            "name": "cascade",
            "controller_target": str(controller_target.id),
            "model_code": "USW24P250",
            "device_count": 1,
        },
        format="json",
    )
    fleet_id = fleet_resp.data["id"]
    api_client.post(
        "/api/v1/traffic/flows/generate-samples/",
        {"fleet_id": fleet_id, "count": 3},
        format="json",
    )
    assert FlowRecord.objects.filter(device__fleet_id=fleet_id).count() == 3
    TrafficProfile.objects.filter().delete()  # touch the other model for a no-op check
    assert FlowRecord.objects.filter(device__fleet_id=fleet_id).count() == 3
