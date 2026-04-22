from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import FleetViewSet

router = DefaultRouter()
router.register("", FleetViewSet, basename="fleet")

urlpatterns = router.urls
