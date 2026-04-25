from __future__ import annotations

import contextlib

from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from .models import FirmwareBlob
from .serializers import FirmwareBlobSerializer
from .storage import get_storage, hash_and_write
from .tasks import ingest_firmware_blob


class FirmwareBlobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FirmwareBlob.objects.all()
    serializer_class = FirmwareBlobSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "head", "options", "post", "delete"]

    def create(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "multipart field 'file' is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        storage = get_storage()
        digest, storage_key, size = hash_and_write(upload, storage)

        blob, created = FirmwareBlob.objects.get_or_create(
            sha256=digest,
            defaults={
                "filename": upload.name,
                "size_bytes": size,
                "storage_key": storage_key,
                "state": FirmwareBlob.STATE_UPLOADED,
            },
        )
        if created:
            ingest_firmware_blob.delay(str(blob.id))
            # Eager Celery (tests) may already have mutated the row; reload.
            blob.refresh_from_db()

        return Response(
            FirmwareBlobSerializer(blob).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        blob = self.get_object()
        with contextlib.suppress(Exception):  # storage backend can be transient
            get_storage().delete(blob.storage_key)
        blob.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
