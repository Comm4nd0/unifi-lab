from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import VirtualDeviceViewSet

router = DefaultRouter()
router.register("", VirtualDeviceViewSet, basename="virtualdevice")

urlpatterns = router.urls
