#!/usr/bin/env bash
# Restore Postgres from a gzipped pg_dump file.
#
#   ./infra/scripts/restore.sh backups/uvl-20260422-120000.sql.gz
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <dump.sql.gz>" >&2
    exit 2
fi

infile="$1"
if [[ ! -f "$infile" ]]; then
    echo "not found: $infile" >&2
    exit 2
fi

echo "WARNING: this will drop and recreate the uvl database. Continue? [y/N]"
read -r ans
if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
    echo "cancelled"
    exit 1
fi

docker compose -f infra/docker-compose.base.yml exec -T postgres \
    psql -U uvl -d postgres -c "DROP DATABASE IF EXISTS uvl; CREATE DATABASE uvl OWNER uvl;"

gunzip -c "$infile" | docker compose -f infra/docker-compose.base.yml exec -T postgres \
    psql -U uvl -d uvl
