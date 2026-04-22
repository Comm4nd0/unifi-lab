from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import ControllerTargetViewSet

router = DefaultRouter()
router.register("", ControllerTargetViewSet, basename="controllertarget")

urlpatterns = router.urls
