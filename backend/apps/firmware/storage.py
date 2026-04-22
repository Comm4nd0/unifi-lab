"""Pluggable blob storage for firmware uploads.

Backend picked via ``settings.BLOB_BACKEND`` — ``filesystem`` (dev + local
mode) writes under ``settings.BLOB_PATH``; ``s3`` targets MinIO in
production once credentials land.

Keeps a narrow API (``put``, ``open``, ``url_for``, ``delete``) so callers
never have to branch on backend.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Protocol

from django.conf import settings


class BlobStorage(Protocol):
    def put(self, storage_key: str, fileobj: BinaryIO) -> None: ...
    def open(self, storage_key: str) -> BinaryIO: ...
    def url_for(self, storage_key: str) -> str: ...
    def delete(self, storage_key: str) -> None: ...


class FilesystemStorage:
    """Stores blobs on a local directory. Good for dev + local mode."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        # Defensive: no traversal, no absolute keys.
        safe = storage_key.replace("..", "").lstrip("/\\")
        return self.root / safe

    def put(self, storage_key: str, fileobj: BinaryIO) -> None:
        target = self._path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as f:
            for chunk in iter(lambda: fileobj.read(1024 * 1024), b""):
                f.write(chunk)

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key).open("rb")

    def url_for(self, storage_key: str) -> str:
        return f"file://{self._path(storage_key)}"

    def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        if path.exists():
            path.unlink()


class S3Storage:
    """MinIO / S3 backend. Thin placeholder — real boto3 client lands when
    Marco confirms MinIO is provisioned on Luma001."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

    def put(self, storage_key: str, fileobj: BinaryIO) -> None:
        raise NotImplementedError("S3 storage not yet wired — set UVL_BLOB_BACKEND=filesystem")

    def open(self, storage_key: str) -> BinaryIO:
        raise NotImplementedError("S3 storage not yet wired")

    def url_for(self, storage_key: str) -> str:
        return f"s3://{self.bucket}/{storage_key}"

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError("S3 storage not yet wired")


def get_storage() -> BlobStorage:
    backend = getattr(settings, "BLOB_BACKEND", "filesystem")
    if backend == "s3":
        return S3Storage(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_FIRMWARE_BUCKET,
        )
    return FilesystemStorage(settings.BLOB_PATH)


def hash_and_write(
    fileobj: BinaryIO, storage: BlobStorage, prefix: str = "firmware"
) -> tuple[str, str, int]:
    """Stream ``fileobj`` into ``storage`` while computing sha256 and byte count.

    Returns ``(sha256, storage_key, size_bytes)``. Uses a temp key during
    the hash pass and renames once we know the final sha256-based key.
    """
    hasher = hashlib.sha256()
    size = 0
    tmp_key = f"{prefix}/_staging/{os.urandom(8).hex()}.part"

    class _TeeReader:
        def __init__(self, inner: BinaryIO) -> None:
            self._inner = inner

        def read(self, n: int = -1) -> bytes:
            chunk = self._inner.read(n)
            hasher.update(chunk)
            nonlocal size
            size += len(chunk)
            return chunk

    storage.put(tmp_key, _TeeReader(fileobj))  # type: ignore[arg-type]
    digest = hasher.hexdigest()
    final_key = f"{prefix}/{digest}.bin"

    # Filesystem: move the file. S3 would do a copy + delete; we raise
    # earlier in that case.
    if isinstance(storage, FilesystemStorage):
        src = storage._path(tmp_key)
        dst = storage._path(final_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            src.unlink()  # deduplicate — blob already stored
        else:
            src.rename(dst)
    return digest, final_key, size
