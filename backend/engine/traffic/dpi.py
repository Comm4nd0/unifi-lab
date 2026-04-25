"""DPI app/category lookup against the UniFi 9.x fixture.

Pure function, no I/O after first load (lru_cache). Safe to call in the
ticker hot path — the fixture is small (~80 apps) and loads in < 1ms.

Fixture path is resolved relative to this file so it works regardless of
the working directory the worker is launched from.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_FIXTURE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "dpi"
    / "unifi-9.x.json"
)


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    try:
        with _FIXTURE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"categories": [], "apps": []}


@lru_cache(maxsize=256)
def lookup_app(name: str) -> tuple[int, int, str, int | None]:
    """Return ``(app_id, category_id, protocol, port)`` for *name*.

    Falls back to ``(0, 0, "tcp", 443)`` for unknown apps.
    Lookup is case-insensitive; the first match wins.
    """
    db = _load()
    needle = name.lower()
    for app in db.get("apps", []):
        if app.get("name", "").lower() == needle:
            return (
                int(app.get("id", 0)),
                int(app.get("category_id", 0)),
                str(app.get("protocol", "tcp")),
                app.get("port"),  # may be null for ICMP
            )
    return 0, 0, "tcp", 443


def category_name(category_id: int) -> str:
    """Return the human-readable category name for a category ID."""
    db = _load()
    for cat in db.get("categories", []):
        if cat.get("id") == category_id:
            return str(cat.get("name", "Unknown"))
    return "Unknown"


def all_apps() -> list[dict[str, Any]]:
    """Return the full app list from the fixture."""
    return list(_load().get("apps", []))
