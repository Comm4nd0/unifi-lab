"""Firmware multipart upload — stores blob, hashes it, kicks off ingest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.firmware.models import FirmwareBlob


@pytest.fixture
def tmp_blob_path(settings, tmp_path: Path) -> Path:  # type: ignore[no-untyped-def]
    settings.BLOB_PATH = str(tmp_path)
    settings.BLOB_BACKEND = "filesystem"
    return tmp_path


@pytest.mark.django_db
def test_upload_creates_blob_row_and_stores_file(api_client, tmp_blob_path):  # type: ignore[no-untyped-def]
    payload = b"UVL_FIRMWARE_STUB_PAYLOAD" * 64  # ~1.6 KB
    expected_sha = hashlib.sha256(payload).hexdigest()
    upload = SimpleUploadedFile(
        "USW24P250-8.3.42.bin", payload, content_type="application/octet-stream"
    )

    resp = api_client.post("/api/v1/firmware/", {"file": upload}, format="multipart")
    assert resp.status_code == 201, resp.data
    body = resp.data
    assert body["sha256"] == expected_sha
    assert body["size_bytes"] == len(payload)
    assert body["filename"] == "USW24P250-8.3.42.bin"
    # Celery is configured CELERY_TASK_ALWAYS_EAGER in tests, so ingest runs inline.
    assert body["state"] in {FirmwareBlob.STATE_READY, FirmwareBlob.STATE_INGESTING}

    stored = tmp_blob_path / "firmware" / f"{expected_sha}.bin"
    assert stored.exists()
    assert stored.read_bytes() == payload


@pytest.mark.django_db
def test_upload_without_file_returns_400(api_client, tmp_blob_path):  # type: ignore[no-untyped-def]
    resp = api_client.post("/api/v1/firmware/", {}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_duplicate_upload_dedupes_on_sha256(api_client, tmp_blob_path):  # type: ignore[no-untyped-def]
    payload = b"exactly-the-same-bytes"
    up1 = SimpleUploadedFile("a.bin", payload, content_type="application/octet-stream")
    up2 = SimpleUploadedFile("b.bin", payload, content_type="application/octet-stream")

    r1 = api_client.post("/api/v1/firmware/", {"file": up1}, format="multipart")
    r2 = api_client.post("/api/v1/firmware/", {"file": up2}, format="multipart")

    assert r1.status_code == 201
    assert r2.status_code == 200  # already existed
    assert r1.data["id"] == r2.data["id"]
    assert FirmwareBlob.objects.count() == 1


@pytest.mark.django_db
def test_delete_removes_row_and_blob(api_client, tmp_blob_path):  # type: ignore[no-untyped-def]
    payload = b"delete-me"
    upload = SimpleUploadedFile("del.bin", payload, content_type="application/octet-stream")
    resp = api_client.post("/api/v1/firmware/", {"file": upload}, format="multipart")
    blob_id = resp.data["id"]
    stored = tmp_blob_path / "firmware" / f"{resp.data['sha256']}.bin"
    assert stored.exists()

    del_resp = api_client.delete(f"/api/v1/firmware/{blob_id}/")
    assert del_resp.status_code == 204
    assert not FirmwareBlob.objects.filter(pk=blob_id).exists()
    assert not stored.exists()
