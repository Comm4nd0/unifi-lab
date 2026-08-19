# Build the console, then serve everything from one Python image.
FROM node:22-alpine AS console
WORKDIR /console
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml ./
COPY backend/simcore ./simcore
RUN uv pip install --system --no-cache -e ".[prod]"

COPY backend/ ./
# Vite writes the console to ../backend/web, which is /backend/web in the
# build stage above.
COPY --from=console /backend/web ./web

EXPOSE 8003
CMD ["sh", "-c", "python manage.py migrate --no-input && python -m gunicorn config.wsgi:application --bind 0.0.0.0:8003 --workers 3"]
