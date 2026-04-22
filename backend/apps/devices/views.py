from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from .models import VirtualDevice
from .serializers import (
    InformExchangeSerializer,
    VirtualDeviceSerializer,
)
from .services import create_device


class VirtualDeviceViewSet(viewsets.ModelViewSet):
    queryset = VirtualDevice.objects.all()
    serializer_class = VirtualDeviceSerializer
    filterset_fields = ("state", "controller_target", "fleet", "model_code")

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        data = serializer.validated_data
        device = create_device(
            model_code=data["model_code"],
            firmware_version=data.get("firmware_version", ""),
            controller_target_id=(
                str(data["controller_target"].id) if data.get("controller_target") else None
            ),
            fleet_id=str(data["fleet"].id) if data.get("fleet") else None,
        )
        serializer.instance = device

    @action(detail=True, url_path="inform-log", methods=["get"])
    def inform_log(self, request: Request, pk: str | None = None) -> Response:
        device = self.get_object()
        qs = device.inform_exchanges.all()
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = InformExchangeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
