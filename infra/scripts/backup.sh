#!/usr/bin/env bash
# Dump Postgres to ./backups/uvl-YYYYMMDD-HHMMSS.sql.gz
set -euo pipefail

mkdir -p backups
ts="$(date -u +%Y%m%d-%H%M%S)"
outfile="backups/uvl-${ts}.sql.gz"

docker compose -f infra/docker-compose.base.yml exec -T postgres \
    pg_dump -U uvl -d uvl | gzip > "$outfile"

echo "wrote $outfile ($(du -h "$outfile" | cut -f1))"
