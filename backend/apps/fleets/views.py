from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Fleet
from .serializers import FleetSerializer
from .services import instantiate_fleet, pause, resume, teardown


class FleetViewSet(viewsets.ModelViewSet):
    queryset = Fleet.objects.all()
    serializer_class = FleetSerializer

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        fleet = serializer.save(state=Fleet.STATE_CREATING)
        instantiate_fleet(fleet)
        serializer.instance = fleet

    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk: str | None = None) -> Response:
        fleet = pause(self.get_object())
        return Response(self.get_serializer(fleet).data)

    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: str | None = None) -> Response:
        fleet = resume(self.get_object())
        return Response(self.get_serializer(fleet).data)

    @action(detail=True, methods=["post"])
    def teardown(self, request: Request, pk: str | None = None) -> Response:
        fleet = teardown(self.get_object())
        return Response(self.get_serializer(fleet).data, status=status.HTTP_202_ACCEPTED)
