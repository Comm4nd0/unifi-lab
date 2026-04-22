from __future__ import annotations

from rest_framework import viewsets

from .models import FirmwareBlob
from .serializers import FirmwareBlobSerializer


class FirmwareBlobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FirmwareBlob.objects.all()
    serializer_class = FirmwareBlobSerializer
