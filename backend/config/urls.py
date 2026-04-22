"""Root URL configuration.

All application APIs mount under /api/v1/. Django Admin is staff-only and
gated on DEBUG or explicit env var in production.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("controllers/", include("apps.controllers.urls")),
    path("devices/", include("apps.devices.urls")),
    path("firmware/", include("apps.firmware.urls")),
    path("templates/", include("apps.templates.urls")),
    path("blueprints/", include("apps.blueprints.urls")),
    path("fleets/", include("apps.fleets.urls")),
    path("traffic/", include("apps.traffic.urls")),
    path("audit/", include("apps.audit.urls")),
    path("system/", include("apps.system.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "api_v1"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
