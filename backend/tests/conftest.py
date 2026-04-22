from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.controllers.models import ControllerTarget


@pytest.fixture
def admin_user(db) -> User:  # type: ignore[no-untyped-def]
    return User.objects.create_superuser(email="admin@uvl.test", password="test-admin-pw")


@pytest.fixture
def api_client(admin_user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def controller_target(db) -> ControllerTarget:  # type: ignore[no-untyped-def]
    return ControllerTarget.objects.create(
        name="Localhost Lab",
        kind=ControllerTarget.KIND_UOS_SERVER,
        inform_url="https://127.0.0.1",
        api_url="https://127.0.0.1/api",
        api_username="admin",
        api_password="unused",
        verify_tls=False,
    )
