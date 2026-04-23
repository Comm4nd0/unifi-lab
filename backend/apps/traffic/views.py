from __future__ import annotations

import ipaddress
import random
import secrets
from datetime import UTC, datetime, timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.devices.models import VirtualDevice

from .models import FlowRecord, TrafficProfile
from .serializers import FlowRecordSerializer, TrafficProfileSerializer

# Keep the stats endpoint cheap: a window wider than this (or a bucket
# narrower than this) pushes too many rows through Python-side bucketing.
# These match the UI's "last hour / 1min buckets" default and cap the
# worst case at a few hundred buckets per request.
STATS_MAX_WINDOW_MINUTES = 24 * 60
STATS_MIN_BUCKET_SECONDS = 5
STATS_MAX_BUCKET_SECONDS = 60 * 60


class FlowRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FlowRecord.objects.all()
    serializer_class = FlowRecordSerializer
    filterset_fields = ("device", "protocol", "blocked")

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset().select_related("device")
        fleet_id = self.request.query_params.get("fleet")
        if fleet_id:
            qs = qs.filter(device__fleet_id=fleet_id)
        return qs

    @action(detail=False, methods=["post"], url_path="generate-samples")
    def generate_samples(self, request: Request) -> Response:
        """Dev-only: seed N synthetic flows for a given fleet so the UI has content.

        Real flow generation happens in the Traffic Simulator (Phase 3,
        worker-side). This endpoint is a convenience for UX iteration while
        the codec is stubbed — it just writes plausible-looking rows.
        """
        fleet_id = request.data.get("fleet_id")
        count = int(request.data.get("count", 20))
        if not fleet_id:
            return Response({"detail": "fleet_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        devices = list(VirtualDevice.objects.filter(fleet_id=fleet_id))
        if not devices:
            return Response(
                {"detail": f"No devices in fleet {fleet_id}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        apps_pool = [
            ("HTTPS", FlowRecord.PROTOCOL_TCP, 443),
            ("HTTP", FlowRecord.PROTOCOL_TCP, 80),
            ("DNS", FlowRecord.PROTOCOL_UDP, 53),
            ("SSH", FlowRecord.PROTOCOL_TCP, 22),
            ("mDNS", FlowRecord.PROTOCOL_UDP, 5353),
            ("NTP", FlowRecord.PROTOCOL_UDP, 123),
        ]
        rng = random.Random(secrets.token_bytes(8))
        now = timezone.now()
        subnet = ipaddress.ip_network("10.0.0.0/24")
        client_ips = [str(ip) for ip in list(subnet.hosts())[:50]]

        created: list[FlowRecord] = []
        for i in range(count):
            device = rng.choice(devices)
            app, proto, dst_port = rng.choice(apps_pool)
            blocked = rng.random() < 0.08
            flow = FlowRecord.objects.create(
                device=device,
                protocol=proto,
                src_ip=rng.choice(client_ips),
                dst_ip=f"{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
                src_port=rng.randint(32_000, 65_000),
                dst_port=dst_port,
                bytes_tx=rng.randint(100, 500_000),
                bytes_rx=rng.randint(100, 5_000_000),
                application=app,
                blocked=blocked,
                reported_at=now - timedelta(seconds=rng.randint(0, 3_600)),
            )
            created.append(flow)
        return Response(
            {"created": len(created), "fleet_id": str(fleet_id)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        """Windowed, bucketed aggregation over recent flows for charting.

        Query params (all optional):
        - ``window_minutes`` — how far back to look (default 60, max 1440).
        - ``bucket_seconds`` — size of each time bucket (default 60,
          range 5..3600).
        - ``fleet`` / ``device`` — narrow to a fleet or single device.

        Bucketing is done Python-side after pulling the minimal column
        set from the DB. That keeps the query portable (SQLite tests,
        Postgres prod) at the cost of being O(rows-in-window). The
        window/bucket caps above keep that bounded.
        """
        try:
            window_minutes = int(request.query_params.get("window_minutes", 60))
            bucket_seconds = int(request.query_params.get("bucket_seconds", 60))
        except (TypeError, ValueError):
            return Response(
                {"detail": "window_minutes and bucket_seconds must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (1 <= window_minutes <= STATS_MAX_WINDOW_MINUTES):
            return Response(
                {"detail": f"window_minutes must be 1..{STATS_MAX_WINDOW_MINUTES}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (STATS_MIN_BUCKET_SECONDS <= bucket_seconds <= STATS_MAX_BUCKET_SECONDS):
            return Response(
                {
                    "detail": (
                        f"bucket_seconds must be {STATS_MIN_BUCKET_SECONDS}"
                        f"..{STATS_MAX_BUCKET_SECONDS}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        start = now - timedelta(minutes=window_minutes)
        # Floor ``start`` to the bucket edge so every bucket boundary
        # lands on a round multiple of ``bucket_seconds`` — easier to
        # read in the UI and stable across refreshes inside the same
        # bucket. We then size ``bucket_count`` from the floored start
        # up through ``now`` (rounding up) so flows arriving between
        # the last edge and ``now`` still land in a valid bucket.
        start_epoch = int(start.timestamp())
        start_epoch -= start_epoch % bucket_seconds
        start = datetime.fromtimestamp(start_epoch, tz=UTC)

        qs = FlowRecord.objects.filter(reported_at__gte=start)
        fleet_id = request.query_params.get("fleet")
        if fleet_id:
            qs = qs.filter(device__fleet_id=fleet_id)
        device_id = request.query_params.get("device")
        if device_id:
            qs = qs.filter(device_id=device_id)

        # Pre-build the bucket list so empty intervals show up as zeroes
        # rather than gaps — the frontend chart relies on contiguous
        # x-axis samples.
        span_seconds = int((now - start).total_seconds())
        bucket_count = max(1, (span_seconds + bucket_seconds - 1) // bucket_seconds)
        buckets: list[dict] = [
            {
                "t": (start + timedelta(seconds=i * bucket_seconds))
                .replace(microsecond=0)
                .isoformat(),
                "allowed": 0,
                "blocked": 0,
                "bytes_tx": 0,
                "bytes_rx": 0,
            }
            for i in range(bucket_count)
        ]

        totals = {"allowed": 0, "blocked": 0, "bytes_tx": 0, "bytes_rx": 0}

        # ``.only`` avoids hydrating relations; the aggregation is
        # lightweight enough that iterating a few hundred rows per
        # refresh is fine for the MVP.
        for row in qs.only("reported_at", "blocked", "bytes_tx", "bytes_rx").iterator(
            chunk_size=1000
        ):
            idx = int((row.reported_at - start).total_seconds()) // bucket_seconds
            if 0 <= idx < bucket_count:
                slot = buckets[idx]
                if row.blocked:
                    slot["blocked"] += 1
                    totals["blocked"] += 1
                else:
                    slot["allowed"] += 1
                    totals["allowed"] += 1
                slot["bytes_tx"] += row.bytes_tx
                slot["bytes_rx"] += row.bytes_rx
                totals["bytes_tx"] += row.bytes_tx
                totals["bytes_rx"] += row.bytes_rx

        return Response(
            {
                "window_minutes": window_minutes,
                "bucket_seconds": bucket_seconds,
                "start": start.replace(microsecond=0).isoformat(),
                "buckets": buckets,
                "totals": totals,
            }
        )


class TrafficProfileViewSet(viewsets.ModelViewSet):
    queryset = TrafficProfile.objects.all()
    serializer_class = TrafficProfileSerializer
