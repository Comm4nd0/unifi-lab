from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import FlowRecordViewSet

router = DefaultRouter()
router.register("flows", FlowRecordViewSet, basename="flowrecord")

urlpatterns = router.urls
