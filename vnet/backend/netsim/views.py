"""HTTP surface for the lab. Thin views over :mod:`netsim.services`."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.request import Request
from rest_framework.response import Response

from netsim import services
from netsim.models import Client, Device, Flow, Link, Network, Port, Site
from netsim.seed import seed_demo_site
from netsim.serializers import (
    ClientSerializer,
    DeviceSerializer,
    FlowSerializer,
    LinkSerializer,
    NetworkSerializer,
    PortSerializer,
    SiteSerializer,
)
from simcore.catalog import CATALOG
from simcore.topology import CABLE_MAX_MBPS, LinkError


class SiteScopedViewSet(viewsets.ModelViewSet):
    """Every collection under a site supports ``?site=<id>``."""

    site_lookup = "site"

    def get_queryset(self):
        queryset = super().get_queryset()
        site_id = self.request.query_params.get("site")
        if site_id:
            queryset = queryset.filter(**{self.site_lookup: site_id})
        return queryset


class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer

    @action(detail=True, methods=["get"])
    def simulation(self, request: Request, pk: str | None = None) -> Response:
        """Run every analysis pass and return the whole console payload."""
        site = self.get_object()
        raw_t = request.query_params.get("t")
        result = services.run_simulation(site, float(raw_t) if raw_t else None)
        return Response(result.to_dict())

    @action(detail=True, methods=["get"])
    def issues(self, request: Request, pk: str | None = None) -> Response:
        result = services.run_simulation(self.get_object())
        return Response([issue.to_dict() for issue in result.issues])

    @action(detail=True, methods=["get"], url_path="available-ports")
    def available_ports(self, request: Request, pk: str | None = None) -> Response:
        site = self.get_object()
        device_id = request.query_params.get("device")
        device = Device.objects.filter(pk=device_id, site=site).first() if device_id else None
        ports = services.available_ports(site, device)
        return Response(PortSerializer(ports, many=True).data)

    @action(detail=True, methods=["get", "post"])
    def blueprint(
        self, request: Request, pk: str | None = None
    ) -> Response | HttpResponse:
        site = self.get_object()
        body = request.data if isinstance(request.data, dict) else {}
        if request.method == "GET":
            blueprint = services.export_blueprint(site)
            if request.query_params.get("as") == "yaml":
                return HttpResponse(
                    yaml.safe_dump(blueprint, sort_keys=False),
                    content_type="application/yaml",
                )
            return Response(blueprint)
        payload = body.get("blueprint", request.data)
        if isinstance(payload, str):
            payload = yaml.safe_load(payload)
        try:
            new_site = services.import_blueprint(payload, body.get("name"))
        except (KeyError, ValueError, LinkError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SiteSerializer(new_site).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="seed-demo")
    def seed_demo(self, request: Request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        site = seed_demo_site(body.get("name", "Chiltern View"))
        return Response(SiteSerializer(site).data, status=status.HTTP_201_CREATED)


class DeviceViewSet(SiteScopedViewSet):
    queryset = Device.objects.select_related("site").prefetch_related("ports")
    serializer_class = DeviceSerializer

    @action(detail=True, methods=["post"])
    def position(self, request: Request, pk: str | None = None) -> Response:
        """Cheap endpoint for canvas drags — avoids a full device round trip."""
        device = self.get_object()
        body = request.data if isinstance(request.data, dict) else {}
        device.x = float(body.get("x", device.x))
        device.y = float(body.get("y", device.y))
        device.save(update_fields=["x", "y"])
        return Response({"id": device.pk, "x": device.x, "y": device.y})


class PortViewSet(viewsets.ModelViewSet):
    queryset = Port.objects.select_related("device")
    serializer_class = PortSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        site_id = self.request.query_params.get("site")
        device_id = self.request.query_params.get("device")
        if site_id:
            queryset = queryset.filter(device__site_id=site_id)
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        return queryset


class LinkViewSet(SiteScopedViewSet):
    queryset = Link.objects.select_related("a_port__device", "b_port__device")
    serializer_class = LinkSerializer


class ClientViewSet(SiteScopedViewSet):
    queryset = Client.objects.select_related("port__device", "access_point")
    serializer_class = ClientSerializer


class FlowViewSet(SiteScopedViewSet):
    queryset = Flow.objects.all()
    serializer_class = FlowSerializer


class NetworkViewSet(SiteScopedViewSet):
    queryset = Network.objects.all()
    serializer_class = NetworkSerializer


@api_view(["GET"])
def catalog(request: Request) -> Response:
    """The full UniFi hardware catalogue the designer can pick from."""
    line = request.query_params.get("line")
    models = [spec.to_dict() for spec in CATALOG if not line or spec.line == line]
    return Response(
        {
            "version": CATALOG.version,
            "cables": dict(CABLE_MAX_MBPS),
            "models": models,
        }
    )


def spa(request, resource: str = "") -> HttpResponse:
    """Serve the built console, or a hint if the frontend has not been built."""
    if resource.startswith(("api/", "static/")):
        return JsonResponse({"detail": "Not found."}, status=404)
    index = Path(settings.BASE_DIR) / "web" / "index.html"
    if index.exists():
        return HttpResponse(index.read_text(), content_type="text/html")
    return HttpResponse(
        json.dumps(
            {
                "detail": "Console not built yet.",
                "hint": "Run `npm --prefix vnet/frontend run build` and restart.",
                "api": "/api/",
                "docs": "/api/docs/",
            },
            indent=2,
        ),
        content_type="application/json",
        status=200,
    )
