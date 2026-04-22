from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiToken
from .serializers import ApiTokenSerializer, UserSerializer


class ApiTokenViewSet(viewsets.ReadOnlyModelViewSet):
    """List and inspect API tokens for the current user.

    Token creation flow emits a one-time plaintext and lives in a dedicated
    endpoint (not yet wired in Phase 0).
    """

    serializer_class = ApiTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return ApiToken.objects.none()
        return ApiToken.objects.filter(user=self.request.user).order_by("-created_at")


class MeView(APIView):
    """Return the authenticated user's profile.

    Djoser exposes /users/me/ as well, but this alias is what the vault's
    API design names explicitly.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)
