from django.urls import include, path
from rest_framework.routers import DefaultRouter

from netsim import views

router = DefaultRouter()
router.register("sites", views.SiteViewSet)
router.register("devices", views.DeviceViewSet)
router.register("ports", views.PortViewSet)
router.register("links", views.LinkViewSet)
router.register("clients", views.ClientViewSet)
router.register("flows", views.FlowViewSet)
router.register("networks", views.NetworkViewSet)

urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("", include(router.urls)),
]
