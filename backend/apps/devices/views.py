from __future__ import annotations

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.pagination import InformExchangeCursor
from apps.common.permissions import IsWorkerRequest
from apps.common.worker_commands import CHANNEL_DEVICES, publish_worker_command

from .models import VirtualDevice
from .serializers import (
    InformExchangeSerializer,
    VirtualDeviceSerializer,
)
from .services import create_device


class VirtualDeviceViewSet(viewsets.ModelViewSet):
    queryset = VirtualDevice.objects.all()
    serializer_class = VirtualDeviceSerializer
    filterset_fields = ("state", "controller_target", "fleet", "model_code")

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        data = serializer.validated_data
        device = create_device(
            model_code=data["model_code"],
            firmware_version=data.get("firmware_version", ""),
            controller_target_id=(
                str(data["controller_target"].id) if data.get("controller_target") else None
            ),
            fleet_id=str(data["fleet"].id) if data.get("fleet") else None,
        )
        serializer.instance = device
        publish_worker_command(
            CHANNEL_DEVICES,
            action="spawn",
            device_id=str(device.id),
        )

    @action(detail=True, url_path="inform-log", methods=["get"])
    def inform_log(self, request: Request, pk: str | None = None) -> Response:
        device = self.get_object()
        qs = device.inform_exchanges.all()
        paginator = InformExchangeCursor()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = InformExchangeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, url_path="force-inform", methods=["post"])
    def force_inform(self, request: Request, pk: str | None = None) -> Response:
        """Ask the supervisor to immediately send a heartbeat for this device."""
        device = self.get_object()
        publish_worker_command(
            CHANNEL_DEVICES,
            action="force_inform",
            device_id=str(device.id),
        )
        return Response(
            {"accepted": True, "device_id": str(device.id)},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def disconnect(self, request: Request, pk: str | None = None) -> Response:
        """Simulate a device disconnect — flips state, asks supervisor to despawn."""
        device = self.get_object()
        device.state = VirtualDevice.STATE_DISCONNECTED
        device.save(update_fields=["state"])
        publish_worker_command(
            CHANNEL_DEVICES,
            action="despawn",
            device_id=str(device.id),
        )
        return Response(VirtualDeviceSerializer(device).data)

    @action(detail=True, methods=["post"])
    def reconnect(self, request: Request, pk: str | None = None) -> Response:
        """Simulate a device reconnect — flips back to pending, re-spawns."""
        device = self.get_object()
        device.state = VirtualDevice.STATE_PENDING
        device.save(update_fields=["state"])
        publish_worker_command(
            CHANNEL_DEVICES,
            action="spawn",
            device_id=str(device.id),
        )
        return Response(VirtualDeviceSerializer(device).data)

    @action(
        detail=True,
        methods=["post"],
        authentication_classes=[],
        permission_classes=[IsWorkerRequest],
    )
    def heartbeat(self, request: Request, pk: str | None = None) -> Response:
        """Worker callback — updates last_heartbeat_at for this device.

        Gated on the worker's shared bearer (``UVL_WORKER_TOKEN``) — no
        user session or JWT required. Authentication classes are blanked
        so DRF's JWTAuthentication doesn't try to parse the worker's
        bearer as a JWT.
        """
        device = self.get_object()
        device.last_heartbeat_at = timezone.now()
        device.save(update_fields=["last_heartbeat_at", "updated_at"])
        return Response(
            {"device_id": str(device.id), "last_heartbeat_at": device.last_heartbeat_at.isoformat()}
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="mark-adopted",
        authentication_classes=[],
        permission_classes=[IsWorkerRequest],
    )
    def mark_adopted(self, request: Request, pk: str | None = None) -> Response:
        """Worker callback — the controller has accepted this device.

        Flips state to ``adopted`` and bumps ``last_heartbeat_at``. Gated
        on the worker's shared bearer (``UVL_WORKER_TOKEN``) — no user
        session or JWT required. Idempotent: subsequent calls with the
        device already adopted just return the current row.

        Authentication classes are blanked so DRF's JWTAuthentication
        doesn't try to parse the worker's bearer as a JWT (which would
        401 before the permission check runs).
        """
        device = self.get_object()
        if device.state != VirtualDevice.STATE_ADOPTED:
            device.state = VirtualDevice.STATE_ADOPTED
            device.last_heartbeat_at = timezone.now()
            device.save(update_fields=["state", "last_heartbeat_at"])
        return Response(VirtualDeviceSerializer(device).data)
