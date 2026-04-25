"""Unit tests for backend/engine/traffic/dpi.py."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_dpi_cache():
    """Clear lru_cache between tests so fixture patches take effect."""
    from engine.traffic import dpi
    dpi._load.cache_clear()
    dpi.lookup_app.cache_clear()
    yield
    dpi._load.cache_clear()
    dpi.lookup_app.cache_clear()


# ── Fixture loading ───────────────────────────────────────────────────────────

def test_fixture_loads_without_error():
    from engine.traffic.dpi import _load
    data = _load()
    assert isinstance(data, dict)
    assert "apps" in data
    assert "categories" in data


def test_fixture_has_apps():
    from engine.traffic.dpi import all_apps
    apps = all_apps()
    assert len(apps) > 0


def test_fixture_app_count_reasonable():
    from engine.traffic.dpi import all_apps
    apps = all_apps()
    # Fixture should have at least 50 apps; we built 88
    assert len(apps) >= 50


def test_fixture_has_categories():
    from engine.traffic.dpi import _load
    cats = _load().get("categories", [])
    assert len(cats) > 0


# ── lookup_app — known apps ───────────────────────────────────────────────────

@pytest.mark.parametrize("app_name,expected_proto,expected_port", [
    ("DNS",       "udp", 53),
    ("HTTPS",     "tcp", 443),
    ("HTTP",      "tcp", 80),
    ("SSH",       "tcp", 22),
    ("FTP",       "tcp", 21),
    ("SMTP",      "tcp", 25),
    ("SMB",       "tcp", 445),
    ("NTP",       "udp", 123),
])
def test_lookup_known_app(app_name, expected_proto, expected_port):
    from engine.traffic.dpi import lookup_app
    _app_id, _cat_id, proto, port = lookup_app(app_name)
    assert proto == expected_proto, f"{app_name}: expected proto={expected_proto}, got {proto}"
    assert port == expected_port, f"{app_name}: expected port={expected_port}, got {port}"


def test_lookup_returns_nonzero_ids_for_known_app():
    from engine.traffic.dpi import lookup_app
    app_id, cat_id, _proto, _port = lookup_app("HTTPS")
    assert app_id > 0
    assert cat_id >= 0


def test_lookup_unknown_app_fallback():
    from engine.traffic.dpi import lookup_app
    app_id, cat_id, proto, port = lookup_app("UnknownApp_XYZ_9999")
    assert app_id == 0
    assert cat_id == 0
    assert proto == "tcp"
    assert port == 443


def test_lookup_case_insensitive():
    from engine.traffic.dpi import lookup_app
    lower = lookup_app("https")
    upper = lookup_app("HTTPS")
    mixed = lookup_app("Https")
    assert lower == upper == mixed


def test_lookup_streaming_apps_exist():
    from engine.traffic.dpi import lookup_app
    for app in ("YouTube", "Netflix", "Spotify", "Zoom", "Slack"):
        app_id, _cat, proto, port = lookup_app(app)
        assert app_id > 0, f"{app} not found in fixture"
        assert proto in ("tcp", "udp")
        assert port is not None


# ── lookup_app — return type ──────────────────────────────────────────────────

def test_lookup_return_is_four_tuple():
    from engine.traffic.dpi import lookup_app
    result = lookup_app("DNS")
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_lookup_port_can_be_none():
    """ICMP-like entries may have null port — lookup should return None, not crash."""
    from engine.traffic.dpi import lookup_app
    # ICMP entry in fixture has port=null
    _id, _cat, proto, port = lookup_app("ICMP")
    assert proto in ("icmp", "tcp", "udp")  # whatever the fixture says
    # port may be None (valid) or an int — just ensure no exception


# ── category_name ─────────────────────────────────────────────────────────────

def test_category_name_known():
    from engine.traffic.dpi import category_name, lookup_app
    _id, cat_id, _proto, _port = lookup_app("DNS")
    name = category_name(cat_id)
    assert isinstance(name, str)
    assert len(name) > 0
    assert name != "Unknown"


def test_category_name_unknown_id():
    from engine.traffic.dpi import category_name
    name = category_name(99999)
    assert name == "Unknown"


def test_category_name_for_https():
    from engine.traffic.dpi import category_name, lookup_app
    _id, cat_id, _proto, _port = lookup_app("HTTPS")
    name = category_name(cat_id)
    assert isinstance(name, str)


# ── all_apps ──────────────────────────────────────────────────────────────────

def test_all_apps_returns_list_of_dicts():
    from engine.traffic.dpi import all_apps
    apps = all_apps()
    assert isinstance(apps, list)
    for app in apps:
        assert isinstance(app, dict)


def test_all_apps_each_has_required_fields():
    from engine.traffic.dpi import all_apps
    for app in all_apps():
        assert "id" in app, f"App missing 'id': {app}"
        assert "name" in app, f"App missing 'name': {app}"
        assert "protocol" in app, f"App missing 'protocol': {app}"


def test_all_apps_ids_unique():
    from engine.traffic.dpi import all_apps
    ids = [a["id"] for a in all_apps()]
    assert len(ids) == len(set(ids)), "Duplicate app IDs in fixture"


def test_all_apps_names_unique():
    from engine.traffic.dpi import all_apps
    names = [a["name"].lower() for a in all_apps()]
    assert len(names) == len(set(names)), "Duplicate app names in fixture"
