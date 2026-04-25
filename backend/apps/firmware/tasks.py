"""Celery tasks for firmware ingestion.

Pipeline: download blob → binwalk scan → squashfs extract → identify model
from /etc/board.info + /usr/lib/version → upsert DeviceTemplate rows.
Progress events are pushed to the ``firmware.<blob_id>`` Channels group.
"""

from __future__ import annotations

import contextlib
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from .models import FirmwareBlob
from .storage import get_storage

log = logging.getLogger("uvl.firmware")


# ── progress helpers ──────────────────────────────────────────────────────────


def _push_progress(
    blob_id: str,
    step: str,
    detail: str = "",
    *,
    error: bool = False,
) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    payload: dict[str, Any] = {
        "blob_id": blob_id,
        "step": step,
        "detail": detail,
        "error": error,
    }
    with contextlib.suppress(Exception):  # never let progress push break the task
        async_to_sync(layer.group_send)(
            f"firmware.{blob_id}",
            {"type": "firmware.progress", "payload": payload},
        )


# ── main task ─────────────────────────────────────────────────────────────────


@shared_task(name="firmware.ingest")
def ingest_firmware_blob(blob_id: str) -> None:
    try:
        blob = FirmwareBlob.objects.get(pk=blob_id)
    except FirmwareBlob.DoesNotExist:
        log.warning("firmware.ingest: blob %s not found", blob_id)
        return

    blob.state = FirmwareBlob.STATE_INGESTING
    blob.save(update_fields=["state"])
    _push_progress(blob_id, "ingesting", "Starting pipeline")

    with tempfile.TemporaryDirectory(prefix="uvl-fw-") as workdir:
        try:
            _run_pipeline(blob, Path(workdir))
        except Exception as exc:
            log.exception("firmware.ingest: pipeline failed for %s", blob_id)
            blob.state = FirmwareBlob.STATE_FAILED
            blob.ingest_error = str(exc)
            blob.save(update_fields=["state", "ingest_error"])
            _push_progress(blob_id, "failed", str(exc), error=True)


# ── pipeline steps ────────────────────────────────────────────────────────────


def _run_pipeline(blob: FirmwareBlob, workdir: Path) -> None:
    # 1. Download from storage
    _push_progress(str(blob.id), "download", "Fetching blob from storage")
    storage = get_storage()
    fw_path = workdir / blob.filename
    with storage.open(blob.storage_key) as src:
        fw_path.write_bytes(src.read())

    # 2. Locate squashfs offsets via binwalk
    _push_progress(str(blob.id), "scan", "Scanning with binwalk")
    offsets = _binwalk_offsets(fw_path)
    log.info("firmware.ingest: %s — found %d squashfs offset(s)", blob.filename, len(offsets))

    model_codes: list[str] = []
    version = ""
    caps: dict[str, int] = {}

    if offsets:
        # Try first offset; fall through to filename heuristic on any failure
        squash_dir = workdir / "squashfs-root"
        try:
            _push_progress(str(blob.id), "extract", f"Extracting squashfs at offset {offsets[0]}")
            _extract_squashfs(fw_path, offsets[0], squash_dir)
            model_codes, version = _identify_from_fs(squash_dir, blob.filename)
            caps = _extract_caps(squash_dir)
        except Exception as exc:
            log.warning("firmware.ingest: squashfs extract failed (%s) — using filename heuristic", exc)

    if not model_codes:
        model_codes, version = _identify_from_filename(blob.filename)

    log.info("firmware.ingest: identified models=%s version=%s caps=%s", model_codes, version, caps)

    # 3. Upsert DeviceTemplate rows
    _push_progress(str(blob.id), "templates", f"Updating {len(model_codes)} template(s)")
    _update_templates(model_codes, version, caps)

    # 4. Mark blob ready
    blob.model_codes = model_codes
    blob.version = version
    blob.state = FirmwareBlob.STATE_READY
    blob.ingest_error = ""
    blob.save(update_fields=["model_codes", "version", "state", "ingest_error"])
    _push_progress(str(blob.id), "ready", f"Done — {len(model_codes)} model(s) identified")


# ── binwalk ───────────────────────────────────────────────────────────────────


def _binwalk_offsets(fw_path: Path) -> list[int]:
    try:
        result = subprocess.run(
            ["binwalk", "--quiet", str(fw_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        log.warning("binwalk not installed — skipping squashfs scan")
        return []
    except subprocess.TimeoutExpired:
        log.warning("binwalk timed out on %s", fw_path.name)
        return []

    offsets: list[int] = []
    for line in result.stdout.splitlines():
        if "squashfs" in line.lower():
            parts = line.strip().split()
            if parts:
                with contextlib.suppress(ValueError):
                    offsets.append(int(parts[0]))
    return offsets


# ── squashfs extraction ───────────────────────────────────────────────────────


def _extract_squashfs(fw_path: Path, offset: int, dest: Path) -> None:
    try:
        result = subprocess.run(
            ["unsquashfs", "-d", str(dest), "-o", str(offset), "-f", str(fw_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("unsquashfs not installed; add squashfs-tools to the container") from exc

    if result.returncode != 0:
        raise RuntimeError(f"unsquashfs failed (rc={result.returncode}): {result.stderr[:500]}")


# ── identification ────────────────────────────────────────────────────────────


def _identify_from_fs(squash_dir: Path, filename: str) -> tuple[list[str], str]:
    board_info = squash_dir / "etc" / "board.info"
    version_file = squash_dir / "usr" / "lib" / "version"

    model_codes: list[str] = []
    version = ""

    if board_info.exists():
        for line in board_info.read_text(errors="replace").splitlines():
            if line.startswith("board.shortname="):
                code = line.split("=", 1)[1].strip()
                if code:
                    model_codes.append(code)

    if version_file.exists():
        raw = version_file.read_text(errors="replace").strip()
        # e.g. "6.6.58.14777" or "UDM.3.2.7.9018"
        match = re.search(r"[\d]+\.[\d.]+", raw)
        version = match.group(0) if match else raw[:32]

    if not model_codes:
        model_codes, fallback_version = _identify_from_filename(filename)
        if not version:
            version = fallback_version

    return model_codes, version


def _identify_from_filename(filename: str) -> tuple[list[str], str]:
    stem = Path(filename).stem
    # e.g. "U6-Lite-6.6.58.14777", "UAP-AC-Lite-firmware-5.43.36"
    match = re.search(r"([A-Za-z][A-Za-z0-9\-]+?)[-_](\d+[\.\d]+)", stem)
    if match:
        raw_model = match.group(1).rstrip("-")
        version = match.group(2)
        model_code = raw_model.upper()
        return [model_code], version
    return [], ""


def _extract_caps(squash_dir: Path) -> dict[str, int]:
    board_info = squash_dir / "etc" / "board.info"
    caps: dict[str, int] = {}
    if not board_info.exists():
        return caps
    for line in board_info.read_text(errors="replace").splitlines():
        if line.startswith("port.count="):
            with contextlib.suppress(ValueError):
                caps["port_count"] = int(line.split("=", 1)[1].strip())
        elif line.startswith("radio.count="):
            with contextlib.suppress(ValueError):
                caps["radio_count"] = int(line.split("=", 1)[1].strip())
    return caps


def _guess_family(model_code: str) -> str:
    mc = model_code.upper()
    if mc.startswith(("U6-", "U7-", "UAP", "UAP-")):
        return "ap"
    if mc.startswith(("USW", "US-")):
        return "switch"
    if mc.startswith(("UDR", "UDM", "USG", "UCG")):
        return "gateway"
    return "other"


# ── template upsert ───────────────────────────────────────────────────────────


def _update_templates(model_codes: list[str], version: str, caps: dict[str, int]) -> None:
    from apps.templates.models import DeviceTemplate

    for code in model_codes:
        family = _guess_family(code)
        hardware_caps: dict[str, Any] = {}
        if caps:
            hardware_caps.update(caps)
        DeviceTemplate.objects.update_or_create(
            model_code=code,
            defaults={
                "model_display": code,
                "device_family": family,
                "hardware_capabilities": hardware_caps,
                "schema_version": f"uvl-template/{version or 'unknown'}",
            },
        )
