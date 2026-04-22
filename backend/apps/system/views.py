"""System health + meta endpoints."""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


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
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "db": _probe_db(),
                "redis": _probe_redis(),
                "version": "0.1.0",
            }
        )
