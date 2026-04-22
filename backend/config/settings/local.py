"""Local / dev settings. SQLite fallback, debug on, permissive CORS/CSRF."""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS

DEBUG = True

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8003",
        "http://127.0.0.1:8003",
        "http://localhost:5173",
    ]

# In dev, Channels can fall back to an in-memory layer if Redis is absent.
# This keeps `manage.py check` green without Redis running.
import os as _os  # noqa: E402

if not _os.environ.get("UVL_CHANNELS_LAYER_URL"):
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }
