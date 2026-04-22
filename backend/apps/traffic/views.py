from __future__ import annotations

from rest_framework import viewsets

from .models import FlowRecord
from .serializers import FlowRecordSerializer


class FlowRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FlowRecord.objects.all()
    serializer_class = FlowRecordSerializer
    filterset_fields = ("device", "protocol", "blocked")
