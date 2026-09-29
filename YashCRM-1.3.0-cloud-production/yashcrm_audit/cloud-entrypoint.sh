#!/bin/sh
set -eu

echo "Applying database migrations..."
alembic upgrade head

echo "Starting Yash CRM cloud service..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
