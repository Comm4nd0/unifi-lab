"""Shared DRF permissions.

``IsScoped`` checks that the authenticated credential (JWT or ApiToken) has a
specific scope in its ``scopes`` list. JWT tokens get the full admin scope
bag; ApiTokens carry an explicit scope list on the row.

``IsWorkerRequest`` gates endpoints the asyncio worker calls back into
Django with. The caller must present ``Authorization: Bearer <token>``
matching ``settings.WORKER_TOKEN`` (backed by env ``UVL_WORKER_TOKEN``).
The comparison is constant-time. If the token isn't configured the
endpoint stays locked, which is what we want in production.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsScoped(permissions.BasePermission):
    """Permission factory keyed on a required scope string."""

    def __init__(self, required_scope: str) -> None:
        self.required_scope = required_scope

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_admin", False) or getattr(user, "is_superuser", False):
            return True
        token = getattr(request, "auth", None)
        scopes: list[str] = getattr(token, "scopes", []) or []
        return self.required_scope in scopes

    def __call__(self) -> IsScoped:
        return self


class IsWorkerRequest(permissions.BasePermission):
    """Authenticate a worker-to-Django callback via a shared bearer token."""

    _SCHEME = "Bearer "

    def has_permission(self, request: Request, view: APIView) -> bool:
        expected = getattr(settings, "WORKER_TOKEN", "") or ""
        if not expected:
            return False
        auth_header: str = request.META.get("HTTP_AUTHORIZATION", "") or ""
        if not auth_header.startswith(self._SCHEME):
            return False
        supplied = auth_header[len(self._SCHEME) :]
        return secrets.compare_digest(supplied.encode(), expected.encode())
