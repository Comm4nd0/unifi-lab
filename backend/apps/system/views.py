"""System endpoints — health, readiness, version, Prometheus metrics, worker heartbeat."""

from __future__ import annotations

from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsWorkerRequest

VERSION = "0.1.0"

WORKER_HEARTBEAT_KEY = "uvl:worker:heartbeat"
# TTL well above the 30s worker cadence so a single dropped beat doesn't
# flip the dashboard to red; three missed beats (90s) does.
WORKER_HEARTBEAT_TTL_SECONDS = 90


def _redis_client():  # type: ignore[no-untyped-def]
    """Return a redis client configured from the Channels layer, or None.

    Used only by the ``_probe_redis`` health check; the worker heartbeat
    goes through Django's cache abstraction which transparently handles
    LocMemCache (dev) vs redis-backed cache (prod).
    """
    url = (
        getattr(settings, "CHANNEL_LAYERS", {})
        .get("default", {})
        .get("CONFIG", {})
        .get("hosts", [])
    )
    if not url:
        return None
    try:
        import redis

        return redis.from_url(url[0] if isinstance(url, list) else url)
    except Exception:
        return None


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


class WorkerHeartbeatView(APIView):
    """Worker → Django heartbeat sink.

    The asyncio engine POSTs to this endpoint every ~30s. We store the
    latest beat in Django's cache with a TTL of
    ``WORKER_HEARTBEAT_TTL_SECONDS``, so if the worker dies the key
    disappears and the status endpoint reports ``alive: false`` without
    needing an explicit cleanup job. ``django.core.cache`` abstracts over
    LocMemCache (dev) and redis-backed caches (prod).

    Body is optional metadata — the worker may include ``pid``,
    ``version``, ``started_at`` — and is round-tripped via the status
    endpoint for display in the UI.
    """

    authentication_classes = []  # worker bearer, not JWT
    permission_classes = [IsWorkerRequest]

    def post(self, request: Request) -> Response:
        now_iso = datetime.now(tz=UTC).isoformat()
        payload = {
            "last_heartbeat_at": now_iso,
            "metadata": request.data if isinstance(request.data, dict) else {},
        }
        try:
            cache.set(WORKER_HEARTBEAT_KEY, payload, timeout=WORKER_HEARTBEAT_TTL_SECONDS)
            recorded = True
        except Exception:
            recorded = False
        return Response({"recorded": recorded, "last_heartbeat_at": now_iso})


class WorkerStatusView(APIView):
    """Dashboard surface — is the engine process alive?"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            data = cache.get(WORKER_HEARTBEAT_KEY)
        except Exception:
            data = None
        if not isinstance(data, dict):
            return Response({"alive": False, "last_heartbeat_at": None, "metadata": {}})
        return Response(
            {
                "alive": True,
                "last_heartbeat_at": data.get("last_heartbeat_at"),
                "metadata": data.get("metadata") or {},
            }
        )


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
