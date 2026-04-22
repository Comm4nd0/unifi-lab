from __future__ import annotations

from rest_framework import viewsets

from .models import Blueprint
from .serializers import BlueprintSerializer


class BlueprintViewSet(viewsets.ModelViewSet):
    queryset = Blueprint.objects.all()
    serializer_class = BlueprintSerializer
