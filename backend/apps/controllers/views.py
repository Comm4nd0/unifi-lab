from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from engine.clients.unifi import UnifiApiError, UosServerClient

from .models import ControllerTarget
from .serializers import ControllerSecretsSerializer, ControllerTargetSerializer

log = logging.getLogger("uvl.controllers.probe")


def _tcp_probe(url: str) -> str | None:
    """Quick reachability check. Returns ``None`` on success so the
    caller can continue with the API probe; otherwise the health string.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return ControllerTarget.HEALTH_UNKNOWN
        with socket.create_connection((host, port), timeout=3):
            return None
    except (OSError, ValueError):
        return ControllerTarget.HEALTH_UNREACHABLE


async def _api_login_probe(ctrl: ControllerTarget) -> str:
    """Attempt an actual controller login via ``UosServerClient``.

    Distinguishes auth rejection from network failures so operators can
    tell "wrong password" from "controller down". Never raises — always
    returns a ``HEALTH_*`` constant.
    """
    try:
        async with UosServerClient(
            base_url=ctrl.api_url,
            username=ctrl.api_username,
            password=ctrl.api_password,
            kind=ctrl.kind,
            verify_tls=ctrl.verify_tls,
            timeout=5.0,
        ) as client:
            await client.login()
    except UnifiApiError as exc:
        if 400 <= exc.status < 500:
            return ControllerTarget.HEALTH_AUTH_FAILED
        return ControllerTarget.HEALTH_UNREACHABLE
    except Exception:
        log.exception("controller.probe.login.failed", extra={"controller": str(ctrl.id)})
        return ControllerTarget.HEALTH_UNREACHABLE
    return ControllerTarget.HEALTH_OK


def _probe_controller(ctrl: ControllerTarget) -> str:
    """Two-stage health probe: TCP reach, then real API login.

    - URL is unparseable or hostname is missing → ``unknown``.
    - TCP connect to the inform URL fails → ``unreachable``.
    - Login returns 4xx → ``auth-failed``.
    - Login returns 5xx, network error, or any other exception → ``unreachable``.
    - Login succeeds → ``ok``.
    """
    tcp_result = _tcp_probe(ctrl.inform_url)
    if tcp_result is not None:
        return tcp_result
    return async_to_sync(_api_login_probe)(ctrl)


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
