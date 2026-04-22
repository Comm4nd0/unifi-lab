from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import BlueprintViewSet

router = DefaultRouter()
router.register("", BlueprintViewSet, basename="blueprint")

urlpatterns = router.urls
