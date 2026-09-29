#!/bin/sh
set -eu

case "${PORT:-8000}" in
  ''|*[!0-9]*) echo "PORT must be a number" >&2; exit 1 ;;
esac

echo "Applying database migrations..."
python -m alembic upgrade head

echo "Starting Yash CRM cloud service..."
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
