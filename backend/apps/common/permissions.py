"""Shared DRF permissions.

``IsScoped`` checks that the authenticated credential (JWT or ApiToken) has a
specific scope in its ``scopes`` list. JWT tokens get the full admin scope
bag; ApiTokens carry an explicit scope list on the row.
"""
from __future__ import annotations

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
        # Admin users bypass scope checks.
        if getattr(user, "is_admin", False) or getattr(user, "is_superuser", False):
            return True
        # When authenticated via an ApiToken, the token will be attached to request.auth.
        token = getattr(request, "auth", None)
        scopes: list[str] = getattr(token, "scopes", []) or []
        return self.required_scope in scopes

    def __call__(self) -> "IsScoped":
        return self
