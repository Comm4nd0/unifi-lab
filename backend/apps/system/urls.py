from __future__ import annotations

from django.urls import path

from .views import HealthView, MetricsView, ReadyzView, VersionView

urlpatterns = [
    path("health/", HealthView.as_view(), name="system-health"),
    path("readyz/", ReadyzView.as_view(), name="system-readyz"),
    path("version/", VersionView.as_view(), name="system-version"),
    path("metrics/", MetricsView.as_view(), name="system-metrics"),
]
