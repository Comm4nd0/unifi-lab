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

    @action(detail=True, methods=["post"], url_path="traffic/start")
    def traffic_start(self, request: Request, pk: str | None = None) -> Response:
        """Activate traffic profiles whose ``applies_to.fleet`` targets this fleet."""
        fleet = self.get_object()
        updated = _set_fleet_traffic(fleet, active=True)
        return Response({"fleet": str(fleet.id), "profiles_activated": updated})

    @action(detail=True, methods=["post"], url_path="traffic/stop")
    def traffic_stop(self, request: Request, pk: str | None = None) -> Response:
        """Deactivate traffic profiles targeting this fleet."""
        fleet = self.get_object()
        updated = _set_fleet_traffic(fleet, active=False)
        return Response({"fleet": str(fleet.id), "profiles_deactivated": updated})


def _set_fleet_traffic(fleet: Fleet, *, active: bool) -> int:
    from apps.traffic.models import TrafficProfile

    fleet_id = str(fleet.id)
    # Django JSONField double-underscore traversal: parsed_json -> applies_to -> fleet
    qs = TrafficProfile.objects.filter(
        parsed_json__applies_to__fleet=fleet_id,
    ) | TrafficProfile.objects.filter(
        parsed_json__applies_to__fleet_id=fleet_id,
    )
    return qs.update(is_active=active)
