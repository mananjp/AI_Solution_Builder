#!/bin/sh
set -e

echo "Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${UVICORN_WORKERS:-2}"