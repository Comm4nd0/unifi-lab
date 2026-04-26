from __future__ import annotations

import json
import logging
import socket
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from engine.clients.unifi import UnifiApiError, UosServerClient
from engine.protocol.codec import decode_inform, encode_inform
from engine.protocol.keys import DEFAULT_INFORM_KEY

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


UNIFI_ERROR_HINTS: dict[str, str] = {
    "api.err.Invalid": "invalid username or password",
    "api.err.LoginRequired": "controller refused anonymous login request",
    "api.err.UbicCloudAccount": (
        "this is a Ubiquiti cloud account — create a local-access admin"
        " in the controller's Admins & Users settings"
    ),
    "api.err.Ubic2faTokenRequired": (
        "account requires 2FA — the API cannot complete an MFA challenge;"
        " use a local admin without MFA"
    ),
    "api.err.AccountLocked": "account is locked after too many failed logins",
    "api.err.NoPermission": "account lacks permission to log in via the API",
}


def _decode_login_error(exc: UnifiApiError) -> str:
    """Turn a raw UnifiApiError from login() into user-facing copy.

    The controller usually returns ``{"meta":{"rc":"error","msg":"api.err.Xxx"}}``;
    we map the handful of common codes to plain-English hints. Unknown codes
    still surface as ``<status>: <msg>`` so operators see the real signal.
    """
    import json as _json
    import re as _re

    raw = (exc.message or "").removeprefix("login failed: ")
    code: str | None = None
    body_match = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if body_match:
        try:
            data = _json.loads(body_match.group(0))
            meta = data.get("meta") or {}
            candidate = meta.get("msg")
            if isinstance(candidate, str):
                code = candidate
        except (ValueError, TypeError):
            pass
    if code:
        friendly = UNIFI_ERROR_HINTS.get(code)
        if friendly:
            return f"{friendly} ({code})"
        return f"controller error {code} (status {exc.status})"
    snippet = raw[:140].replace("\n", " ").strip()
    return f"status {exc.status}" + (f" · {snippet}" if snippet else "")


async def _probe_login(ctrl: ControllerTarget) -> tuple[str, str, int | None]:
    """Run the UniFi API login and translate errors into (status, detail, http_status).

    ``http_status`` is the controller's HTTP response code when available,
    or ``None`` for network/TLS errors. Never raises.
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
        return "failed", _decode_login_error(exc), exc.status
    except Exception as exc:
        log.exception("controller.probe.login.failed", extra={"controller": str(ctrl.id)})
        return "failed", f"connection error: {type(exc).__name__}", None
    return "ok", "login accepted, session established", 200


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
        steps.append(
            _step(STEP_PARSE_URL, "failed", "inform URL missing hostname", elapsed_ms=parse_elapsed)
        )
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
    login_status, login_detail, http_status = async_to_sync(_probe_login)(ctrl)
    login_elapsed = int((time.monotonic() - t0) * 1000)
    steps.append(_step(STEP_API_LOGIN, login_status, login_detail, elapsed_ms=login_elapsed))
    if login_status == "ok":
        return ControllerTarget.HEALTH_OK, steps
    if http_status is not None and 400 <= http_status < 500:
        return ControllerTarget.HEALTH_AUTH_FAILED, steps
    return ControllerTarget.HEALTH_UNREACHABLE, steps


class ControllerTargetViewSet(viewsets.ModelViewSet):
    queryset = ControllerTarget.objects.all()
    serializer_class = ControllerTargetSerializer

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        """Auto-populate inform/API URLs for virtual controllers."""
        ctrl = serializer.save()
        if ctrl.kind == ControllerTarget.KIND_VIRTUAL:
            _auto_configure_virtual(ctrl, self.request)

    def perform_update(self, serializer):  # type: ignore[no-untyped-def]
        ctrl = serializer.save()
        if ctrl.kind == ControllerTarget.KIND_VIRTUAL:
            _auto_configure_virtual(ctrl, self.request)

    @action(
        detail=True,
        methods=["post"],
        url_path="inform",
        authentication_classes=[],
        permission_classes=[AllowAny],
    )
    def inform(self, request: Request, pk: str | None = None) -> HttpResponse:
        """Virtual UDM — accepts TNBU inform frames and responds with commands.

        Unauthenticated endpoint (the device uses the inform key, not JWT).
        Only works for controllers with ``kind='virtual'``.
        """
        ctrl = self.get_object()
        if ctrl.kind != ControllerTarget.KIND_VIRTUAL:
            return HttpResponse(b"not a virtual controller", status=400)
        return _handle_virtual_inform(ctrl, request)

    @action(detail=True, methods=["post"], url_path="health-check")
    def health_check(self, request: Request, pk: str | None = None) -> Response:
        ctrl = self.get_object()
        old_health = ctrl.health

        # Virtual controllers are always healthy — no external probing needed.
        if ctrl.kind == ControllerTarget.KIND_VIRTUAL:
            health = ControllerTarget.HEALTH_OK
            steps = [
                _step(STEP_PARSE_URL, "ok", "virtual controller — local endpoint"),
                _step(STEP_TCP_CONNECT, "ok", "built-in, no network needed"),
                _step(STEP_API_LOGIN, "ok", "virtual — no credentials required"),
            ]
        else:
            health, steps = _probe_controller(ctrl)
        ctrl.health = health
        ctrl.last_verified_at = timezone.now()
        ctrl.save(update_fields=["health", "last_verified_at"])

        # Notify on health transition
        if health != old_health:
            from apps.system.notifications import push as notify

            if health == "ok":
                notify(
                    title=f"Controller “{ctrl.name}” is healthy",
                    message="All health check steps passed",
                    level="success",
                    target_type="controller",
                    target_id=str(ctrl.id),
                )
            else:
                notify(
                    title=f"Controller “{ctrl.name}” is {health}",
                    message=steps[-1].get("detail", "") if steps else "",
                    level="warning" if health == "degraded" else "error",
                    target_type="controller",
                    target_id=str(ctrl.id),
                )

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


# --- Virtual UDM helpers --------------------------------------------------


def _auto_configure_virtual(ctrl: ControllerTarget, request: Request) -> None:
    """Set inform_url and api_url to point at this Django instance."""
    base = request.build_absolute_uri("/").rstrip("/")
    ctrl.inform_url = f"{base}/api/v1/controllers/{ctrl.id}/inform/"
    ctrl.api_url = f"{base}/api/v1/controllers/{ctrl.id}/"
    ctrl.health = ControllerTarget.HEALTH_OK
    ctrl.last_verified_at = timezone.now()
    ctrl.save(update_fields=["inform_url", "api_url", "health", "last_verified_at"])


def _handle_virtual_inform(ctrl: ControllerTarget, request: Request) -> HttpResponse:
    """Process an incoming TNBU inform frame for a virtual controller.

    Decodes the frame, looks up the device by MAC, determines the right
    command (adopt on first contact, noop for heartbeats), encodes a
    response frame, and records the exchange. Returns binary TNBU.
    """
    from apps.devices.models import InformExchange, VirtualDevice

    body = request.body
    if not body:
        return HttpResponse(b"empty body", status=400)

    key = DEFAULT_INFORM_KEY

    # Decode the incoming inform frame
    try:
        payload_in = decode_inform(body, key=key)
    except Exception as exc:
        log.warning("virtual_inform.decode_failed", extra={"error": str(exc)})
        return HttpResponse(b"decode failed", status=400)

    mac = str(payload_in.get("mac", "")).lower()
    if not mac:
        return HttpResponse(b"no mac in payload", status=400)

    # Look up the device
    device = VirtualDevice.objects.filter(mac_address__iexact=mac).first()
    exchange_type = InformExchange.TYPE_HEARTBEAT

    # Build the response — adopt if pending, noop otherwise
    now_iso = timezone.now().isoformat()
    if device and device.state == VirtualDevice.STATE_PENDING:
        # First contact: adopt the device
        response_payload: dict[str, Any] = {
            "_type": "setparam",
            "cmd": "set-default",
            "server_time_in_utc": now_iso,
            "mgmt_cfg": json.dumps({
                "authkey": DEFAULT_INFORM_KEY.hex(),
                "cfgversion": "virtual-001",
                "selfrun_guest_mode": "off",
            }),
        }
        exchange_type = InformExchange.TYPE_ADOPT
        # Auto-adopt: flip to adopted
        device.state = VirtualDevice.STATE_ADOPTED
        device.last_heartbeat_at = timezone.now()
        device.save(update_fields=["state", "last_heartbeat_at", "updated_at"])
    else:
        response_payload = {
            "_type": "noop",
            "cmd": "noop",
            "server_time_in_utc": now_iso,
            "interval": 10,
        }
        if device:
            device.last_heartbeat_at = timezone.now()
            device.save(update_fields=["last_heartbeat_at", "updated_at"])

    # Encode the response
    mac_bytes = bytes.fromhex(mac.replace(":", ""))
    response_frame = encode_inform(
        payload=response_payload, key=key, mac=mac_bytes, use_gcm=True
    )

    # Record the exchange
    if device:
        InformExchange.objects.create(
            id=uuid.uuid4(),
            device=device,
            exchange_type=exchange_type,
            payload_in=payload_in,
            payload_out=response_payload,
            exchanged_at=timezone.now(),
        )

    return HttpResponse(response_frame, content_type="application/x-binary")
