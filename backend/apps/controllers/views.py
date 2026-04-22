from __future__ import annotations

from rest_framework import viewsets

from .models import ControllerTarget
from .serializers import ControllerTargetSerializer


class ControllerTargetViewSet(viewsets.ModelViewSet):
    queryset = ControllerTarget.objects.all()
    serializer_class = ControllerTargetSerializer
