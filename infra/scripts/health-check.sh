#!/usr/bin/env bash
# Curl the UVL health endpoint. Exits non-zero on non-200.
set -euo pipefail

URL="${1:-http://localhost:8003/api/v1/system/health/}"
curl -fsS "$URL" | python3 -c "import json, sys; d = json.load(sys.stdin); print(json.dumps(d, indent=2)); sys.exit(0 if d.get('status') == 'ok' else 1)"
