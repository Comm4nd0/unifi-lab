"""Settings for the UniFi Virtual Lab API.

The lab is a single-tenant, self-hosted tool, so the defaults here are tuned for
running it on a laptop or on Luma001 behind Caddy rather than for a public SaaS.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("UVL_SECRET_KEY", "dev-only-not-for-production")
DEBUG = os.environ.get("UVL_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("UVL_ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.environ.get("UVL_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "netsim",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("UVL_DB_PATH", str(BASE_DIR / "uvl.sqlite3")),
    }
}
if os.environ.get("UVL_POSTGRES_HOST"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("UVL_POSTGRES_DB", "uvl"),
        "USER": os.environ.get("UVL_POSTGRES_USER", "uvl"),
        "PASSWORD": os.environ.get("UVL_POSTGRES_PASSWORD", ""),
        "HOST": os.environ["UVL_POSTGRES_HOST"],
        "PORT": os.environ.get("UVL_POSTGRES_PORT", "5432"),
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# The built console lands in backend/web. WhiteNoise serves that directory at
# the site root so /assets/... resolves before the SPA catch-all route.
WHITENOISE_ROOT = BASE_DIR / "web"
WHITENOISE_INDEX_FILE = True
WHITENOISE_AUTOREFRESH = DEBUG
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

REST_FRAMEWORK = {
    # The lab holds no secrets and is meant to run on a trusted network or
    # behind Caddy's own auth. Put a real permission class here before exposing it.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "UniFi Virtual Lab API",
    "DESCRIPTION": "Design, simulate and troubleshoot virtual UniFi networks.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin
    for origin in os.environ.get("UVL_CORS_ORIGINS", "").split(",")
    if origin
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("UVL_LOG_LEVEL", "INFO")},
}
