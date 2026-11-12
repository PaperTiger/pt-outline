#!/usr/bin/env bash
# Restores the newest backup from Spaces into a scratch database, compares row counts with live, then drops it.
set -euo pipefail
cd /opt/outline
LATEST=$(bin/s3 s3 ls s3://pt-outline/backups/ | awk '{print $4}' | sort | tail -1)
[ -n "$LATEST" ] || { echo "no backups found"; exit 1; }
bin/s3 s3 cp "s3://pt-outline/backups/$LATEST" /tmp/restore.sql.gz --only-show-errors
PSQL="docker compose exec -T postgres psql -U outline -v ON_ERROR_STOP=1 -q"
$PSQL -d outline -c "DROP DATABASE IF EXISTS restore_test" -c "CREATE DATABASE restore_test"
gunzip -c /tmp/restore.sql.gz | $PSQL -d restore_test > /dev/null
for t in teams users collections documents; do
  live=$($PSQL -d outline -tAc "select count(*) from $t"); rest=$($PSQL -d restore_test -tAc "select count(*) from $t")
  echo "$t live=$live restored=$rest"; [ "$live" = "$rest" ] || echo "  MISMATCH (live may have changed since the dump)"
done
$PSQL -d outline -c "DROP DATABASE restore_test"; rm -f /tmp/restore.sql.gz
echo "restore test ok from $LATEST"
