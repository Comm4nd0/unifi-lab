from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import ApiTokenViewSet, MeView

router = DefaultRouter()
router.register("tokens", ApiTokenViewSet, basename="apitoken")

# Djoser provides /users/, /users/me/, /users/set_password/, /users/reset_password/, etc.
# We layer explicit JWT endpoints under /jwt/ for direct login/refresh/verify/blacklist.
urlpatterns = [
    path("", include("djoser.urls")),
    path("jwt/create/", TokenObtainPairView.as_view(), name="jwt-create"),
    path("jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("jwt/verify/", TokenVerifyView.as_view(), name="jwt-verify"),
    path("jwt/blacklist/", TokenBlacklistView.as_view(), name="jwt-blacklist"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
