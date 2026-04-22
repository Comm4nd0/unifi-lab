"""Blueprint validator — JSON Schema + semantic checks.

Two passes:
1. Structural — JSON Schema (``schemas/blueprint.v1.json``).
2. Semantic — the pieces JSON Schema can't express naturally: hostname
   uniqueness, WLAN/network cross-references, uplink resolution,
   model_code has a DeviceTemplate in our catalogue.

Returns ``ValidationResult`` with a ``valid`` flag and a list of
``ValidationIssue`` objects (``severity``, ``path``, ``message``).
Never raises on bad data; always returns a structured response so the
editor can render inline errors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(settings.BASE_DIR).parent / "schemas" / "blueprint.v1.json"


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    path: str  # JSON pointer-ish dotted path
    message: str


@dataclass
class ValidationResult:
    valid: bool
    parsed: dict[str, Any] | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, severity: str, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(severity, path, message))

    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


def parse_yaml(source: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse YAML; return (dict, error_message). Never raises."""
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"
    if not isinstance(data, dict):
        return None, "Top-level blueprint document must be a mapping"
    return data, None


def validate(data: dict[str, Any]) -> ValidationResult:
    result = ValidationResult(valid=False, parsed=data)

    validator = Draft202012Validator(_schema())
    for err in validator.iter_errors(data):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        result.add("error", path, err.message)

    if not result.has_errors():
        _semantic_checks(data, result)

    result.valid = not result.has_errors()
    return result


def _semantic_checks(data: dict[str, Any], result: ValidationResult) -> None:
    site = data.get("site", {})
    networks = {n["name"]: n for n in site.get("networks", []) if "name" in n}
    devices = site.get("devices", [])
    wlans = site.get("wlans", [])

    # Hostname uniqueness
    seen: dict[str, int] = {}
    for idx, dev in enumerate(devices):
        hostname = dev.get("hostname")
        if not hostname:
            continue
        if hostname in seen:
            result.add(
                "error",
                f"site.devices[{idx}].hostname",
                f"Duplicate hostname {hostname!r} (also at devices[{seen[hostname]}])",
            )
        else:
            seen[hostname] = idx

    # WLAN network cross-reference
    for idx, wlan in enumerate(wlans):
        ref = wlan.get("network")
        if ref and ref not in networks:
            result.add(
                "error",
                f"site.wlans[{idx}].network",
                f"WLAN references unknown network {ref!r}",
            )

    # Device uplink resolves
    for idx, dev in enumerate(devices):
        uplink = dev.get("uplink")
        if uplink and uplink not in seen:
            result.add(
                "error",
                f"site.devices[{idx}].uplink",
                f"Uplink references unknown hostname {uplink!r}",
            )

    # Device model_code known (warning only — we may upload the matching
    # firmware after authoring the blueprint).
    from apps.templates.models import DeviceTemplate

    known_models = set(DeviceTemplate.objects.values_list("model_code", flat=True))
    for idx, dev in enumerate(devices):
        model = dev.get("model")
        if model and model not in known_models:
            result.add(
                "warning",
                f"site.devices[{idx}].model",
                f"No DeviceTemplate for model {model!r} — upload matching firmware before instantiation",
            )
