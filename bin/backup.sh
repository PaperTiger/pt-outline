#!/usr/bin/env bash
# Nightly Postgres dump to Spaces (s3://pt-outline/backups/). A lifecycle rule deletes dumps after 30 days.
set -euo pipefail
cd /opt/outline
STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
FILE=/opt/outline/logs/outline-$STAMP.sql.gz
docker compose exec -T postgres pg_dump -U outline -d outline --no-owner | gzip > "$FILE"
[ "$(stat -c %s "$FILE")" -gt 1000 ] || { echo "dump too small, aborting"; exit 1; }
/opt/outline/bin/s3 s3 cp "$FILE" "s3://pt-outline/backups/outline-$STAMP.sql.gz" --only-show-errors
rm -f "$FILE"
echo "$(date -u +%FT%TZ) backup ok: backups/outline-$STAMP.sql.gz"
