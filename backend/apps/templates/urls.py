from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import DeviceTemplateViewSet

router = DefaultRouter()
router.register("", DeviceTemplateViewSet, basename="devicetemplate")

urlpatterns = router.urls
