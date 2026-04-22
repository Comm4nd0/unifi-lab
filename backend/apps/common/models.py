"""Abstract models shared across all apps."""

from __future__ import annotations

from django.db import models

from .uuid import uuid7


class TimestampedModel(models.Model):
    """Adds created_at / updated_at to any model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """UUIDv7 primary key — time-ordered, safe for sharding and log correlation."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimestampedModel):
    class Meta:
        abstract = True
