"""Celery tasks for firmware ingestion.

Real binwalk integration lives in a later phase. This stub marks blobs as
ready without actually extracting anything.
"""

from __future__ import annotations

from celery import shared_task

from .models import FirmwareBlob


@shared_task(name="firmware.ingest")
def ingest_firmware_blob(blob_id: str) -> None:
    try:
        blob = FirmwareBlob.objects.get(pk=blob_id)
    except FirmwareBlob.DoesNotExist:
        return
    blob.state = FirmwareBlob.STATE_INGESTING
    blob.save(update_fields=["state"])
    # TODO: run binwalk + extract metadata into templates.DeviceTemplate
    blob.state = FirmwareBlob.STATE_READY
    blob.save(update_fields=["state"])
