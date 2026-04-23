from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import FlowRecordViewSet, TrafficProfileViewSet

router = DefaultRouter()
router.register("flows", FlowRecordViewSet, basename="flowrecord")
router.register("profiles", TrafficProfileViewSet, basename="trafficprofile")

urlpatterns = router.urls
