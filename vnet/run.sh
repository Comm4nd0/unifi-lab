#!/usr/bin/env bash
# Bring the whole lab up in one command: build the console, prepare the
# database, seed an example site the first time, then serve on port 8003.
#
#   ./run.sh            build everything and serve
#   ./run.sh --api      skip the console build (use with `npm run dev`)
#   ./run.sh --fresh    throw the database away and start over
set -euo pipefail

cd "$(dirname "$0")"
BUILD_CONSOLE=1
FRESH=0
for arg in "$@"; do
  case "$arg" in
    --api) BUILD_CONSOLE=0 ;;
    --fresh) FRESH=1 ;;
    -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "$1 is required but not installed." >&2; exit 1; }; }
need python3

if [ "$BUILD_CONSOLE" = 1 ]; then
  need npm
  echo "==> Building the console"
  ( cd frontend && [ -d node_modules ] || npm install --no-audit --no-fund )
  ( cd frontend && npm run build )
fi

cd backend

if command -v uv >/dev/null 2>&1; then
  [ -d .venv ] || uv venv
  echo "==> Installing backend dependencies"
  uv pip install -q -e ".[dev]"
else
  [ -d .venv ] || python3 -m venv .venv
  echo "==> Installing backend dependencies"
  .venv/bin/pip install -q -e ".[dev]"
fi
PY=.venv/bin/python

export UVL_DB_PATH="${UVL_DB_PATH:-$PWD/uvl.sqlite3}"
[ "$FRESH" = 1 ] && rm -f "$UVL_DB_PATH"

echo "==> Preparing the database"
$PY manage.py migrate --no-input

# `manage.py shell -c` prints an auto-import banner, so ask Django directly.
SITE_COUNT=$($PY -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from netsim.models import Site
print(Site.objects.count())
")
if [ "$SITE_COUNT" = "0" ]; then
  echo "==> Seeding an example site"
  $PY manage.py seed_demo
fi

PORT="${UVL_PORT:-8003}"
echo
echo "    Console  http://localhost:$PORT"
echo "    API      http://localhost:$PORT/api/"
echo "    Docs     http://localhost:$PORT/api/docs/"
echo
exec $PY manage.py runserver "0.0.0.0:$PORT"
