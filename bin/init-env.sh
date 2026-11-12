#!/usr/bin/env bash
# Writes /opt/outline/.env. Generates internal secrets once; keeps any values already set.
set -euo pipefail
ENV=/opt/outline/.env
touch "$ENV"; chmod 600 "$ENV"
setv() { grep -q "^$1=" "$ENV" || printf '%s=%s\n' "$1" "$2" >> "$ENV"; }
force() { grep -v "^$1=" "$ENV" > "$ENV.tmp" || true; printf '%s=%s\n' "$1" "$2" >> "$ENV.tmp"; mv "$ENV.tmp" "$ENV"; chmod 600 "$ENV"; }

# Generated once, never printed
setv SECRET_KEY "$(openssl rand -hex 32)"
setv UTILS_SECRET "$(openssl rand -hex 32)"
setv POSTGRES_PASSWORD "$(openssl rand -hex 24)"
PW=$(grep '^POSTGRES_PASSWORD=' "$ENV" | cut -d= -f2)

# Fixed settings (re-applied on every run)
force NODE_ENV production
force URL https://papertiger.agency
force PORT 3000
force FORCE_HTTPS true
force WEB_CONCURRENCY 1
force DEFAULT_LANGUAGE en_US
force ENABLE_UPDATES false
force DATABASE_URL "postgres://outline:${PW}@postgres:5432/outline"
force PGSSLMODE disable
force REDIS_URL redis://redis:6379
force FILE_STORAGE s3
force AWS_REGION nyc3
force AWS_S3_UPLOAD_BUCKET_URL https://nyc3.digitaloceanspaces.com
force AWS_S3_UPLOAD_BUCKET_NAME pt-outline
force AWS_S3_FORCE_PATH_STYLE true
force AWS_S3_ACL private
force FILE_STORAGE_UPLOAD_MAX_SIZE 104857600
force SMTP_HOST smtp-relay.gmail.com
force SMTP_PORT 587
force SMTP_SECURE false
force SMTP_NAME papertiger.agency
force SMTP_FROM_EMAIL "Paper Tiger Outline <noreply@papertiger.com>"
force RATE_LIMITER_ENABLED true

# Filled later by Marc with set-secret: GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
echo "env ready; names: $(cut -d= -f1 "$ENV" | tr '\n' ' ')"
