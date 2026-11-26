#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

PROXY_FLAGS=""
if [ "${TRUST_PROXY_HEADERS:-false}" = "true" ]; then
    PROXY_FLAGS="--proxy-headers --forwarded-allow-ips=*"
fi

echo "Starting Coach3 server on port ${PORT:-8000}..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" ${PROXY_FLAGS}

