"""Production settings — strict, HSTS, whitenoise."""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import MIDDLEWARE as _BASE_MIDDLEWARE

DEBUG = False

SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware", *_BASE_MIDDLEWARE]
