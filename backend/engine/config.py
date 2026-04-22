"""Engine runtime configuration — loaded from env, not from Django settings.

The worker is a separate process and must not import Django. It reads the
same UVL_* env vars the Django service uses, re-parsing independently.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    database_url: str
    redis_url: str
    channels_layer_url: str
    django_api_base: str
    log_level: str

    @classmethod
    def from_env(cls) -> EngineConfig:
        return cls(
            database_url=os.environ.get(
                "UVL_DATABASE_URL", "postgres://uvl:uvl@localhost:5432/uvl"
            ),
            redis_url=os.environ.get("UVL_REDIS_URL", "redis://localhost:6379/0"),
            channels_layer_url=os.environ.get("UVL_CHANNELS_LAYER_URL", "redis://localhost:6379/2"),
            django_api_base=os.environ.get("UVL_DJANGO_API_BASE", "http://localhost:8003"),
            log_level=os.environ.get("UVL_LOG_LEVEL", "INFO"),
        )
