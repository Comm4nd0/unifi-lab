#!/usr/bin/env bash
# One-shot bootstrap: apply migrations, create the admin user from env.
set -euo pipefail

cd "$(dirname "$0")/../../backend"

uv run python manage.py migrate --no-input

uv run python manage.py shell <<PY
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ.get("UVL_ADMIN_EMAIL", "admin@uvl.local")
password = os.environ.get("UVL_ADMIN_PASSWORD", "change-me-on-first-login")
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password)
    print(f"created admin {email}")
else:
    print(f"admin {email} already exists")
PY
