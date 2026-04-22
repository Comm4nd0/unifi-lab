# syntax=docker/dockerfile:1.7
# Multi-stage build for UVL backend.
# Targets:
#   app             — Django + Daphne (ASGI HTTP + WebSocket)
#   worker-devices  — asyncio device engine (python -m engine.main)
#   worker-celery   — Celery worker for firmware ingestion
#   local           — all three under supervisord (for single-container mode)

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/* \
 && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --system -r <(uv export --format requirements-txt --no-dev 2>/dev/null || true) \
 && uv pip install --system -e .[dev] || uv pip install --system -e .

COPY . .

# ── app: Django (HTTP + WebSocket via Daphne) ─────────────────────
FROM base AS app
EXPOSE 8003
CMD ["daphne", "-b", "0.0.0.0", "-p", "8003", "config.asgi:application"]

# ── worker-devices: asyncio device engine ─────────────────────────
FROM base AS worker-devices
CMD ["python", "-m", "engine.main"]

# ── worker-celery: firmware ingestion ─────────────────────────────
FROM base AS worker-celery
RUN apt-get update \
 && apt-get install -y --no-install-recommends binwalk \
 && rm -rf /var/lib/apt/lists/*
CMD ["celery", "-A", "config", "worker", "-l", "info"]

# ── local: supervisord running all three ──────────────────────────
FROM base AS local
RUN apt-get update \
 && apt-get install -y --no-install-recommends supervisor binwalk \
 && rm -rf /var/lib/apt/lists/*
COPY ../infra/supervisord/local.conf /etc/supervisor/conf.d/uvl.conf
EXPOSE 8003
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/uvl.conf"]
