from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Blueprint
from .serializers import BlueprintSerializer, BlueprintValidateSerializer


def _unique_clone_name(base: str) -> str:
    """Pick a name that doesn't clash with any existing blueprint.

    Tries ``<base> (copy)`` first, then ``<base> (copy N)`` with N
    increasing until a free slot is found. Bounded by a sanity cap to
    avoid infinite loops on a wildly crowded namespace.
    """
    first = f"{base} (copy)"
    if not Blueprint.objects.filter(name=first).exists():
        return first
    for i in range(2, 1_000):
        candidate = f"{base} (copy {i})"
        if not Blueprint.objects.filter(name=candidate).exists():
            return candidate
    raise ValueError(f"could not find a free clone name for {base!r}")


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

    @action(detail=True, methods=["post"], url_path="clone")
    def clone(self, request: Request, pk: str | None = None) -> Response:
        """Duplicate an existing blueprint. Name suffix " (copy)" added.

        The clone is a new row (fresh id, version reset to 1) with the
        same YAML and parsed shape. The serializer's create path re-parses
        and re-validates to stay consistent with the rest of the CRUD
        surface — cloning a blueprint that would no longer validate (e.g.
        if its referenced models are gone from the catalog) 400s the
        request with the original validation errors.
        """
        src = self.get_object()
        new_name = _unique_clone_name(src.name)
        serializer = self.get_serializer(data={"name": new_name, "source_yaml": src.source_yaml})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
