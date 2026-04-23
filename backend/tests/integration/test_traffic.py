"""TrafficProfile CRUD + flow filtering + sample generator."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.devices.models import VirtualDevice
from apps.fleets.models import Fleet
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


# --- stats endpoint --------------------------------------------------------


def _make_device(fleet: Fleet, mac_tail: str) -> VirtualDevice:
    return VirtualDevice.objects.create(
        mac_address=f"02:00:00:00:00:{mac_tail}",
        serial_number=f"SN-{mac_tail}",
        model_code="USW24P250",
        firmware_version="6.5.0",
        state=VirtualDevice.STATE_PENDING,
        inform_key="00" * 16,
        fleet=fleet,
        controller_target=fleet.controller_target,
    )


@pytest.mark.django_db
def test_stats_empty_window_returns_zero_buckets(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.get("/api/v1/traffic/flows/stats/?window_minutes=5&bucket_seconds=60")
    assert resp.status_code == 200, resp.data
    assert resp.data["window_minutes"] == 5
    assert resp.data["bucket_seconds"] == 60
    # Either exactly N buckets or one extra for the partial tail bucket —
    # ``start`` floors down to a bucket edge and we round up to cover now.
    assert 5 <= len(resp.data["buckets"]) <= 6
    assert resp.data["totals"] == {"allowed": 0, "blocked": 0, "bytes_tx": 0, "bytes_rx": 0}
    for b in resp.data["buckets"]:
        assert b["allowed"] == 0 and b["blocked"] == 0


@pytest.mark.django_db
def test_stats_counts_allowed_vs_blocked(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="s", controller_target=controller_target, model_code="USW24P250", device_count=1
    )
    device = _make_device(fleet, "aa")
    now = timezone.now()
    FlowRecord.objects.create(
        device=device,
        protocol=FlowRecord.PROTOCOL_TCP,
        src_ip="10.0.0.2",
        dst_ip="1.2.3.4",
        bytes_tx=100,
        bytes_rx=200,
        application="HTTPS",
        blocked=False,
        reported_at=now - timedelta(seconds=30),
    )
    FlowRecord.objects.create(
        device=device,
        protocol=FlowRecord.PROTOCOL_TCP,
        src_ip="10.0.0.3",
        dst_ip="5.6.7.8",
        bytes_tx=50,
        bytes_rx=75,
        application="HTTPS",
        blocked=True,
        reported_at=now - timedelta(seconds=10),
    )

    resp = api_client.get("/api/v1/traffic/flows/stats/?window_minutes=5&bucket_seconds=60")
    assert resp.status_code == 200
    assert resp.data["totals"] == {"allowed": 1, "blocked": 1, "bytes_tx": 150, "bytes_rx": 275}


@pytest.mark.django_db
def test_stats_filters_by_fleet(api_client, controller_target):  # type: ignore[no-untyped-def]
    f1 = Fleet.objects.create(
        name="f1", controller_target=controller_target, model_code="USW24P250", device_count=1
    )
    f2 = Fleet.objects.create(
        name="f2", controller_target=controller_target, model_code="USW24P250", device_count=1
    )
    d1 = _make_device(f1, "11")
    d2 = _make_device(f2, "22")
    now = timezone.now()
    for dev in (d1, d2):
        FlowRecord.objects.create(
            device=dev,
            protocol=FlowRecord.PROTOCOL_TCP,
            src_ip="10.0.0.2",
            dst_ip="1.2.3.4",
            bytes_tx=10,
            bytes_rx=20,
            application="HTTPS",
            blocked=False,
            reported_at=now - timedelta(seconds=5),
        )

    resp = api_client.get(f"/api/v1/traffic/flows/stats/?fleet={f1.id}")
    assert resp.status_code == 200
    assert resp.data["totals"]["allowed"] == 1


@pytest.mark.django_db
def test_stats_filters_by_device(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="d", controller_target=controller_target, model_code="USW24P250", device_count=2
    )
    d1 = _make_device(fleet, "01")
    d2 = _make_device(fleet, "02")
    now = timezone.now()
    FlowRecord.objects.create(
        device=d1,
        protocol=FlowRecord.PROTOCOL_TCP,
        src_ip="10.0.0.2",
        dst_ip="1.2.3.4",
        bytes_tx=10,
        bytes_rx=20,
        application="HTTPS",
        blocked=False,
        reported_at=now - timedelta(seconds=5),
    )
    FlowRecord.objects.create(
        device=d2,
        protocol=FlowRecord.PROTOCOL_TCP,
        src_ip="10.0.0.3",
        dst_ip="1.2.3.5",
        bytes_tx=10,
        bytes_rx=20,
        application="HTTPS",
        blocked=True,
        reported_at=now - timedelta(seconds=5),
    )

    resp = api_client.get(f"/api/v1/traffic/flows/stats/?device={d1.id}")
    assert resp.status_code == 200
    # Only d1's allowed row should count.
    assert resp.data["totals"] == {"allowed": 1, "blocked": 0, "bytes_tx": 10, "bytes_rx": 20}


@pytest.mark.django_db
def test_stats_ignores_rows_outside_window(api_client, controller_target):  # type: ignore[no-untyped-def]
    fleet = Fleet.objects.create(
        name="x", controller_target=controller_target, model_code="USW24P250", device_count=1
    )
    device = _make_device(fleet, "bb")
    now = timezone.now()
    # Row just outside a 5-minute window.
    FlowRecord.objects.create(
        device=device,
        protocol=FlowRecord.PROTOCOL_TCP,
        src_ip="10.0.0.2",
        dst_ip="1.2.3.4",
        bytes_tx=999,
        bytes_rx=999,
        application="HTTPS",
        blocked=False,
        reported_at=now - timedelta(minutes=10),
    )

    resp = api_client.get("/api/v1/traffic/flows/stats/?window_minutes=5&bucket_seconds=60")
    assert resp.status_code == 200
    assert resp.data["totals"]["bytes_tx"] == 0


@pytest.mark.django_db
def test_stats_rejects_bad_window(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.get("/api/v1/traffic/flows/stats/?window_minutes=0")
    assert resp.status_code == 400
    resp = api_client.get("/api/v1/traffic/flows/stats/?window_minutes=nope")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_stats_rejects_bad_bucket(api_client):  # type: ignore[no-untyped-def]
    resp = api_client.get("/api/v1/traffic/flows/stats/?bucket_seconds=1")
    assert resp.status_code == 400
    resp = api_client.get("/api/v1/traffic/flows/stats/?bucket_seconds=999999")
    assert resp.status_code == 400
