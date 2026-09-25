#!/usr/bin/env bash
# AI Solution Builder — Unified Container Entrypoint for Generated MVP
# Runs FastAPI backend on 127.0.0.1:8000 and Next.js frontend on 0.0.0.0:${PORT:-3000}.
# Next.js rewrites /api/* requests internally to http://127.0.0.1:8000/api/*.

set -euo pipefail

PORT="${PORT:-3000}"
INTERNAL_API_PORT="${INTERNAL_API_PORT:-8000}"
export CONTAINER_ROLE="unified"

echo "[entrypoint] Starting FastAPI backend on 127.0.0.1:${INTERNAL_API_PORT}..."
(
  cd /app/backend
  python -m uvicorn main:app --host 127.0.0.1 --port "${INTERNAL_API_PORT}" --workers 1
) &
API_PID=$!

echo "[entrypoint] Waiting for FastAPI backend to be ready..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${INTERNAL_API_PORT}/api/v1/health" >/dev/null 2>&1; then
    echo "[entrypoint] FastAPI backend is ready."
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "[entrypoint] ERROR: FastAPI backend exited unexpectedly during startup!"
    exit 1
  fi
  sleep 1
done

echo "[entrypoint] Starting Next.js frontend on 0.0.0.0:${PORT}..."
(
  cd /app/frontend
  HOSTNAME="0.0.0.0" PORT="${PORT}" npm run start
) &
NEXT_PID=$!

trap 'echo "[entrypoint] Shutting down services..."; kill $API_PID $NEXT_PID 2>/dev/null || true; wait' INT TERM
wait -n "$API_PID" "$NEXT_PID" 2>/dev/null || wait
