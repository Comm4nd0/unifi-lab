"""Celery application — used for firmware ingestion only.

Do not reach for Celery for anything stateful or long-lived. Inform heartbeats,
WebSocket fan-out, and fleet supervision live in the asyncio device worker.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("uvl")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):  # type: ignore[no-untyped-def]
    print(f"Request: {self.request!r}")
