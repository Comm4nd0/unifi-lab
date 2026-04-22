"""System endpoints — health, readiness, version, Prometheus metrics."""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

VERSION = "0.1.0"


def _probe_db() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return "ok"
    except Exception:  # pragma: no cover
        return "degraded"


def _probe_redis() -> str:
    url = (
        getattr(settings, "CHANNEL_LAYERS", {})
        .get("default", {})
        .get("CONFIG", {})
        .get("hosts", [])
    )
    if not url:
        return "skipped"
    try:
        import redis

        client = redis.from_url(url[0] if isinstance(url, list) else url)
        client.ping()
        return "ok"
    except Exception:
        return "degraded"


class HealthView(APIView):
    """Liveness probe + component status, public."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "db": _probe_db(),
                "redis": _probe_redis(),
                "version": VERSION,
            }
        )


class ReadyzView(APIView):
    """Readiness probe — returns 503 if required deps are degraded.

    Redis is optional in dev ("skipped" counts as ready).
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        db = _probe_db()
        redis_state = _probe_redis()
        ready = db == "ok" and redis_state in ("ok", "skipped")
        return Response(
            {"ready": ready, "db": db, "redis": redis_state},
            status=200 if ready else 503,
        )


class VersionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"version": VERSION, "phase": "0"})


class MetricsView(APIView):
    """Prometheus exposition, admin-only.

    Returns the raw Prometheus text format; bypasses DRF's JSON renderer.
    """

    permission_classes = [IsAdminUser]

    def get(self, request: Request) -> HttpResponse:
        from apps.controllers.models import ControllerTarget
        from apps.devices.models import InformExchange, VirtualDevice

        lines = [
            "# HELP uvl_controller_targets_total Number of controller targets",
            "# TYPE uvl_controller_targets_total gauge",
            f"uvl_controller_targets_total {ControllerTarget.objects.count()}",
            "# HELP uvl_virtual_devices_total Number of virtual devices",
            "# TYPE uvl_virtual_devices_total gauge",
            f"uvl_virtual_devices_total {VirtualDevice.objects.count()}",
            "# HELP uvl_inform_exchanges_total Number of inform exchange rows",
            "# TYPE uvl_inform_exchanges_total counter",
            f"uvl_inform_exchanges_total {InformExchange.objects.count()}",
        ]
        return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4")
