from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Blueprint
from .serializers import BlueprintSerializer, BlueprintValidateSerializer


class BlueprintViewSet(viewsets.ModelViewSet):
    queryset = Blueprint.objects.all()
    serializer_class = BlueprintSerializer

    @action(
        detail=False,
        methods=["post"],
        url_path="validate",
        permission_classes=[AllowAny],  # editor live-feedback; no DB write
    )
    def validate_source(self, request: Request) -> Response:
        serializer = BlueprintValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data["_result"], status=status.HTTP_200_OK)
