#!/usr/bin/env bash
# Generate UVL runtime secrets. Output is env-var format; pipe to .env.local:
#
#   ./infra/scripts/generate-secrets.sh >> .env.local
#
# Requires: openssl, python3.
set -euo pipefail

django_secret() {
  openssl rand -base64 50 | tr -d '\n='
}

jwt_secret() {
  openssl rand -base64 64 | tr -d '\n='
}

fernet_key() {
  python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
}

cat <<EOF
UVL_SECRET_KEY=$(django_secret)
UVL_JWT_SIGNING_KEY=$(jwt_secret)
UVL_FERNET_KEY=$(fernet_key)
EOF
