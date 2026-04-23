"""ApiToken CRUD surface — list, create (emits plaintext once), revoke."""

from __future__ import annotations

import pytest

from apps.accounts.models import ApiToken


@pytest.mark.django_db
def test_create_returns_plaintext_once_and_never_again(api_client, admin_user):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "ci-bot", "scopes": ["read", "fleet:execute"]},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["name"] == "ci-bot"
    assert set(resp.data["scopes"]) == {"read", "fleet:execute"}
    plaintext = resp.data["token"]
    assert isinstance(plaintext, str) and len(plaintext) >= 30

    # Listing must not leak the plaintext; the digest is server-side only.
    detail = api_client.get(f"/api/v1/auth/tokens/{resp.data['id']}/")
    assert detail.status_code == 200
    assert "token" not in detail.data


@pytest.mark.django_db
def test_create_defaults_to_read_scope_when_empty_list(api_client, admin_user):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "default-scope", "scopes": []},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["scopes"] == ["read"]


@pytest.mark.django_db
def test_create_rejects_unknown_scope(api_client, admin_user):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "bad", "scopes": ["nope"]},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_dedupes_scopes(api_client, admin_user):  # type: ignore[no-untyped-def]
    resp = api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "dup", "scopes": ["read", "read", "write"]},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["scopes"] == ["read", "write"]


@pytest.mark.django_db
def test_list_only_returns_current_users_tokens(api_client, admin_user):  # type: ignore[no-untyped-def]
    from apps.accounts.models import User

    # Own token.
    api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "mine", "scopes": ["read"]},
        format="json",
    )
    # Someone else's token on a different user.
    other = User.objects.create_user(email="other@uvl.test", password="pw")
    ApiToken.generate(user=other, name="not-mine", scopes=["read"])

    resp = api_client.get("/api/v1/auth/tokens/")
    assert resp.status_code == 200
    names = [row["name"] for row in resp.data["results"]]
    assert "mine" in names
    assert "not-mine" not in names


@pytest.mark.django_db
def test_destroy_revokes_token(api_client, admin_user):  # type: ignore[no-untyped-def]
    created = api_client.post(
        "/api/v1/auth/tokens/",
        {"name": "to-revoke", "scopes": ["read"]},
        format="json",
    )
    tid = created.data["id"]
    resp = api_client.delete(f"/api/v1/auth/tokens/{tid}/")
    assert resp.status_code == 204
    assert not ApiToken.objects.filter(pk=tid).exists()


@pytest.mark.django_db
def test_unauthenticated_cannot_list():  # type: ignore[no-untyped-def]
    from rest_framework.test import APIClient

    client = APIClient()
    resp = client.get("/api/v1/auth/tokens/")
    assert resp.status_code == 401
