"""Shared Django middleware.

``RequestIdMiddleware`` — generates/propagates an X-Request-ID per request
and binds it to structlog's contextvars so every log line inside the
request tags along.

``AuditLogMiddleware`` — writes an ``AuditLog`` row for every state-changing
request (POST/PUT/PATCH/DELETE). Runs *after* the response so we can
capture the status code and any response-derived target id.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from apps.common.uuid import uuid7

_REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
_RESPONSE_HEADER = "X-Request-ID"

log = logging.getLogger("uvl.request")


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        req_id = request.META.get(_REQUEST_ID_HEADER) or str(uuid7())
        request.request_id = req_id  # type: ignore[attr-defined]

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=req_id,
            method=request.method,
            path=request.path,
        )

        response = self.get_response(request)
        response[_RESPONSE_HEADER] = req_id
        return response


# ── Audit ─────────────────────────────────────────────────────────────

_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_UUID_IN_PATH_RE = re.compile(
    r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(/|$)",
    re.IGNORECASE,
)
_RESOURCE_FROM_PATH_RE = re.compile(r"/api/v1/([a-z_-]+)/")


def _extract_target(path: str) -> tuple[str, str]:
    resource = ""
    match = _RESOURCE_FROM_PATH_RE.match(path)
    if match:
        resource = match.group(1)
    target_id = ""
    uuid_match = _UUID_IN_PATH_RE.search(path)
    if uuid_match:
        target_id = uuid_match.group(1)
    return resource, target_id


class AuditLogMiddleware(MiddlewareMixin):
    """Emit one AuditLog row per state-changing, authenticated request."""

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if request.method not in _STATE_CHANGING_METHODS:
            return response
        user = getattr(request, "user", None)
        # Skip anonymous requests (login attempts etc are logged at DEBUG, not audited).
        if not user or not getattr(user, "is_authenticated", False):
            return response
        if not request.path.startswith("/api/"):
            return response

        # Deferred import — AuditLog lives in apps.audit and this middleware
        # is referenced from settings.base, which loads before app registry.
        from apps.audit.models import AuditLog

        target_type, target_id = _extract_target(request.path)
        try:
            AuditLog.objects.create(
                actor=user if getattr(user, "pk", None) else None,
                action=f"{request.method} {request.path}",
                target_type=target_type,
                target_id=target_id,
                metadata={
                    "status_code": response.status_code,
                    "request_id": getattr(request, "request_id", ""),
                },
            )
        except Exception:
            # Auditing must never break the request cycle.
            log.exception("audit.write_failed")
        return response
