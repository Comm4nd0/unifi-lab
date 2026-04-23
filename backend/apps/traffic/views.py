from __future__ import annotations

import ipaddress
import random
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.devices.models import VirtualDevice

from .models import FlowRecord, TrafficProfile
from .serializers import FlowRecordSerializer, TrafficProfileSerializer


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


class TrafficProfileViewSet(viewsets.ModelViewSet):
    queryset = TrafficProfile.objects.all()
    serializer_class = TrafficProfileSerializer
