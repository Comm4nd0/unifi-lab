from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import FirmwareBlobViewSet

router = DefaultRouter()
router.register("", FirmwareBlobViewSet, basename="firmwareblob")

urlpatterns = router.urls
