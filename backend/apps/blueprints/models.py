"""Blueprint — declarative YAML description of a site."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Blueprint(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    source_yaml = models.TextField()
    parsed_json = models.JSONField()
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="blueprints",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
