"""Shared Django settings for all deployment modes.

Environment-specific overrides live in local.py, production.py, test.py.
All environment variables are namespaced with UVL_.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env.local", override=False)

# ── Core ──────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("UVL_SECRET_KEY", "django-insecure-change-me-in-prod")
DEBUG = os.environ.get("UVL_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("UVL_ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("UVL_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# ── Encryption key (Fernet) ───────────────────────────────────────
# Used by apps.common.fields.EncryptedTextField for at-rest credentials.
FERNET_KEY = os.environ.get("UVL_FERNET_KEY", "")
FERNET_KEY_PREV = os.environ.get("UVL_FERNET_KEY_PREV", "")

# ── Worker ↔ Django shared bearer ─────────────────────────────────
# The asyncio worker uses this to call back into Django after a
# successful adopt so the device state flips without a user request.
# Empty => the callback endpoint rejects everything.
WORKER_TOKEN = os.environ.get("UVL_WORKER_TOKEN", "")

# ── Installed apps ────────────────────────────────────────────────
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "djoser",
    # UVL apps
    "apps.common",
    "apps.accounts",
    "apps.controllers",
    "apps.devices",
    "apps.firmware",
    "apps.templates",
    "apps.blueprints",
    "apps.fleets",
    "apps.traffic",
    "apps.audit",
    "apps.system",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Database ──────────────────────────────────────────────────────
_default_db = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("UVL_DATABASE_URL", _default_db),
        conn_max_age=60,
    ),
}

# ── Auth ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── I18N ──────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static / media ────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── CORS ──────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("UVL_CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ── DRF ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "SIGNING_KEY": os.environ.get("UVL_JWT_SIGNING_KEY", SECRET_KEY),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=4),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ── Djoser (auth endpoints) ───────────────────────────────────────
# Exposes /api/v1/auth/* for login, refresh, password reset, user CRUD.
DJOSER = {
    "LOGIN_FIELD": "email",
    "USER_CREATE_PASSWORD_RETYPE": False,
    "SEND_ACTIVATION_EMAIL": False,
    "PASSWORD_RESET_CONFIRM_URL": "password/reset/confirm/{uid}/{token}",
    "TOKEN_MODEL": None,  # we use JWT; no DRF token model
    "SERIALIZERS": {},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "UniFi Virtual Lab API",
    "DESCRIPTION": "UVL REST + WebSocket API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ── Channels ──────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("UVL_CHANNELS_LAYER_URL", "redis://localhost:6379/2")],
            "capacity": 1500,
            "expiry": 60,
        },
    }
}

# ── Celery ────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("UVL_CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("UVL_CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# ── Logging ───────────────────────────────────────────────────────
import structlog  # noqa: E402

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "format": '{"level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
            "style": "%",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("UVL_LOG_LEVEL", "INFO"),
    },
}

# ── Blob backend ──────────────────────────────────────────────────
BLOB_BACKEND = os.environ.get("UVL_BLOB_BACKEND", "filesystem")
BLOB_PATH = os.environ.get("UVL_BLOB_PATH", "/var/lib/uvl/blobs")
MINIO_ENDPOINT = os.environ.get("UVL_MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.environ.get("UVL_MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.environ.get("UVL_MINIO_SECRET_KEY", "")
MINIO_FIRMWARE_BUCKET = os.environ.get("UVL_MINIO_FIRMWARE_BUCKET", "uvl-firmware")
