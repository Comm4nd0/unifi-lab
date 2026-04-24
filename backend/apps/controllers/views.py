from __future__ import annotations

import logging
import socket
import time
from typing import Any
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

# --- Step machinery for the UI-facing probe ------------------------------

STEP_PARSE_URL = "parse_url"
STEP_TCP_CONNECT = "tcp_connect"
STEP_API_LOGIN = "api_login"

STEP_LABELS = {
    STEP_PARSE_URL: "Parse inform URL",
    STEP_TCP_CONNECT: "Network reachable",
    STEP_API_LOGIN: "Authenticate API credentials",
}


def _step(name: str, status_: str, detail: str = "", *, elapsed_ms: int | None = None) -> dict:
    """Build a step row for the probe response.

    ``status_`` is one of ``ok`` / ``failed`` / ``skipped`` / ``pending``.
    """
    out: dict[str, Any] = {
        "name": name,
        "label": STEP_LABELS.get(name, name),
        "status": status_,
        "detail": detail,
    }
    if elapsed_ms is not None:
        out["elapsed_ms"] = elapsed_ms
    return out


async def _probe_login(ctrl: ControllerTarget) -> tuple[str, str]:
    """Run the UniFi API login and translate errors into (status, detail).

    Returns a 2-tuple: ``(step_status, detail)``. Never raises.
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
            return "failed", f"controller rejected credentials ({exc.status})"
        return "failed", f"controller returned {exc.status}"
    except Exception as exc:  # noqa: BLE001 - intentional catch-all for probe
        log.exception("controller.probe.login.failed", extra={"controller": str(ctrl.id)})
        return "failed", f"connection error: {type(exc).__name__}"
    return "ok", "login accepted, session established"


def _probe_controller(ctrl: ControllerTarget) -> tuple[str, list[dict]]:
    """Three-stage health probe returning overall status + per-step detail.

    Steps:
      1. parse_url — check the inform URL has a hostname/port we can use
      2. tcp_connect — open a raw socket to host:port
      3. api_login — actually log into the controller's API

    On failure at any step the remaining steps are marked ``skipped``;
    the frontend renders them greyed out.
    """
    steps: list[dict] = []

    # 1. Parse URL
    t0 = time.monotonic()
    parsed = urlparse(ctrl.inform_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    parse_elapsed = int((time.monotonic() - t0) * 1000)
    if not host:
        steps.append(_step(STEP_PARSE_URL, "failed", "inform URL missing hostname", elapsed_ms=parse_elapsed))
        steps.append(_step(STEP_TCP_CONNECT, "skipped"))
        steps.append(_step(STEP_API_LOGIN, "skipped"))
        return ControllerTarget.HEALTH_UNKNOWN, steps
    steps.append(
        _step(STEP_PARSE_URL, "ok", f"{host}:{port} · {parsed.scheme}", elapsed_ms=parse_elapsed)
    )

    # 2. TCP connect
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        steps.append(
            _step(
                STEP_TCP_CONNECT,
                "failed",
                f"cannot reach {host}:{port} · {type(exc).__name__}",
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )
        )
        steps.append(_step(STEP_API_LOGIN, "skipped"))
        return ControllerTarget.HEALTH_UNREACHABLE, steps
    steps.append(
        _step(
            STEP_TCP_CONNECT,
            "ok",
            f"TCP handshake in {int((time.monotonic() - t0) * 1000)}ms",
        )
    )

    # 3. API login
    t0 = time.monotonic()
    login_status, login_detail = async_to_sync(_probe_login)(ctrl)
    login_elapsed = int((time.monotonic() - t0) * 1000)
    steps.append(_step(STEP_API_LOGIN, login_status, login_detail, elapsed_ms=login_elapsed))
    if login_status == "ok":
        return ControllerTarget.HEALTH_OK, steps
    if "rejected credentials" in login_detail:
        return ControllerTarget.HEALTH_AUTH_FAILED, steps
    return ControllerTarget.HEALTH_UNREACHABLE, steps


class ControllerTargetViewSet(viewsets.ModelViewSet):
    queryset = ControllerTarget.objects.all()
    serializer_class = ControllerTargetSerializer

    @action(detail=True, methods=["post"], url_path="health-check")
    def health_check(self, request: Request, pk: str | None = None) -> Response:
        ctrl = self.get_object()
        health, steps = _probe_controller(ctrl)
        ctrl.health = health
        ctrl.last_verified_at = timezone.now()
        ctrl.save(update_fields=["health", "last_verified_at"])
        data = self.get_serializer(ctrl).data
        # ``steps`` is transient — not persisted, only echoed back to
        # the caller so the UI can show each stage. Keeps the Controller
        # serializer focused on durable fields.
        data = {**data, "steps": steps}
        return Response(data)

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
