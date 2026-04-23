from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiToken
from .serializers import (
    ApiTokenCreateSerializer,
    ApiTokenSerializer,
    UserSerializer,
)


class ApiTokenViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """List, create, inspect, and revoke API tokens for the current user.

    Creating a token is the one moment we emit the plaintext — it's
    never stored and cannot be retrieved later. Revocation deletes the
    row (the underlying digest column is unique + CASCADEs to audit
    references via a null on SET_NULL on any future schema).
    """

    serializer_class = ApiTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return ApiToken.objects.none()
        return ApiToken.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = ApiTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, plaintext = ApiToken.generate(
            user=request.user,
            name=serializer.validated_data["name"],
            scopes=serializer.validated_data.get("scopes", ["read"]),
        )
        # Response echoes the standard token shape plus the one-time
        # plaintext. Clients must store this — re-fetching the token
        # later will never include it again.
        data = ApiTokenSerializer(token).data
        return Response({**data, "token": plaintext}, status=status.HTTP_201_CREATED)


class MeView(APIView):
    """Return the authenticated user's profile.

    Djoser exposes /users/me/ as well, but this alias is what the vault's
    API design names explicitly.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)
