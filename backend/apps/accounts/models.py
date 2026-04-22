"""Accounts — email-based users and scoped API tokens."""

from __future__ import annotations

import hashlib
import secrets

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.common.uuid import uuid7


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields: object) -> User:
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> User:
        extra_fields.setdefault("is_admin", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(unique=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        return self.email


class ApiToken(BaseModel):
    """Long-lived, scoped token for machine-to-machine access.

    The token digest is stored, never the token itself. On creation we
    return the plaintext to the caller once and then forget it.
    """

    SCOPE_CHOICES = [
        ("read", "Read"),
        ("write", "Write"),
        ("fleet:execute", "Execute fleets"),
        ("firmware:upload", "Upload firmware"),
        ("admin", "Admin"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=255)
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "name"])]

    def __str__(self) -> str:
        return f"{self.user.email}:{self.name}"

    @classmethod
    def generate(cls, user: User, name: str, scopes: list[str]) -> tuple[ApiToken, str]:
        plaintext = secrets.token_urlsafe(32)
        digest = hashlib.sha256(plaintext.encode()).hexdigest()
        token = cls.objects.create(user=user, name=name, scopes=scopes, token_digest=digest)
        return token, plaintext

    def mark_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])
