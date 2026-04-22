"""Test settings — in-memory SQLite, eager Celery, silent logs."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # fast for tests only
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}

FERNET_KEY = "zX8oq3x_8u_4fQ1TaH5uBvtH1jGHfLbpFZXQyXDjP-Y="  # deterministic test key
