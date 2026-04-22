from __future__ import annotations

from rest_framework import viewsets

from .models import DeviceTemplate
from .serializers import DeviceTemplateSerializer


class DeviceTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceTemplate.objects.all()
    serializer_class = DeviceTemplateSerializer
    lookup_field = "model_code"
