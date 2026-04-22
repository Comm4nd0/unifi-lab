from __future__ import annotations

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import ControllerTarget
from .serializers import ControllerSecretsSerializer, ControllerTargetSerializer


def _probe_controller(ctrl: ControllerTarget) -> str:
    """Lightweight probe. Full UniFi API integration lands once we have
    ``engine.clients.unifi``; for now a basic TCP/TLS reachability check.
    """
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(ctrl.inform_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return ControllerTarget.HEALTH_UNKNOWN
        with socket.create_connection((host, port), timeout=3):
            return ControllerTarget.HEALTH_OK
    except (OSError, ValueError):
        return ControllerTarget.HEALTH_UNREACHABLE


class ControllerTargetViewSet(viewsets.ModelViewSet):
    queryset = ControllerTarget.objects.all()
    serializer_class = ControllerTargetSerializer

    @action(detail=True, methods=["post"], url_path="health-check")
    def health_check(self, request: Request, pk: str | None = None) -> Response:
        ctrl = self.get_object()
        ctrl.health = _probe_controller(ctrl)
        ctrl.last_verified_at = timezone.now()
        ctrl.save(update_fields=["health", "last_verified_at"])
        return Response(self.get_serializer(ctrl).data)

    @action(detail=True, methods=["post"], url_path="secrets")
    def rotate_secrets(self, request: Request, pk: str | None = None) -> Response:
        ctrl = self.get_object()
        serializer = ControllerSecretsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(ctrl, field, value)
        ctrl.save()
        return Response(
            self.get_serializer(ctrl).data,
            status=status.HTTP_200_OK,
        )
