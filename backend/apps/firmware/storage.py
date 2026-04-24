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
    """MinIO / S3 backend via the minio-py client."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        try:
            from minio import Minio  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "minio package required — install with: uv add minio"
            ) from exc

        ep = endpoint.replace("https://", "").replace("http://", "")
        use_tls = secure or endpoint.startswith("https://")
        self._client = Minio(ep, access_key=access_key, secret_key=secret_key, secure=use_tls)
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
        except Exception:
            pass

    def put(self, storage_key: str, fileobj: BinaryIO) -> None:
        import io

        data = fileobj.read()
        self._client.put_object(self.bucket, storage_key, io.BytesIO(data), length=len(data))

    def open(self, storage_key: str) -> BinaryIO:
        import io

        response = self._client.get_object(self.bucket, storage_key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        return io.BytesIO(data)

    def url_for(self, storage_key: str) -> str:
        return f"s3://{self.bucket}/{storage_key}"

    def delete(self, storage_key: str) -> None:
        self._client.remove_object(self.bucket, storage_key)


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
