#!/usr/bin/env bash
# AI Solution Builder — unified container entrypoint
#
# APP_ROLE=app      -> run alembic migration, start FastAPI (127.0.0.1:8000)
#                       and the Next.js server (PORT, proxy /api -> uvicorn).
# APP_ROLE=builder  -> run alembic migration, start opencode serve (4096) and
#                       the background build worker (shared /workspace).
# APP_ROLE=worker   -> legacy alias, worker only (used by local docker-compose).
#
# The first argument may also supply the role (e.g. "app", "builder").

set -euo pipefail

# All Python/alembic tooling and the standalone frontend live under /app when
# running inside the container; the legacy docker-compose variant runs this
# from the backend working directory. Normalize to /app if present, else stay.
cd /app 2>/dev/null || true

ROLE="${1:-${APP_ROLE:-app}}"
: "${PORT:=3000}"
: "${UVICORN_WORKERS:=1}"
: "${ENABLE_OPENCODE_SIDECAR:=false}"
# Debian slim images ship python3; python:3.12-slim also aliases `python`.
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Limit glibc memory arena fragmentation on 512MB RAM machines
export MALLOC_ARENA_MAX=2

log() { echo "[entrypoint] $*"; }

run_migrations() {
  root_dir="${1:-$PWD}"
  log "Running database migrations (advisory-locked alembic upgrade head) in $root_dir ..."
  (cd "$root_dir" && $PYTHON_BIN scripts/run_migrations.py)
  log "Database migrations complete."
}

start_app() {
  log "Starting FastAPI API on 127.0.0.1:8000 with $UVICORN_WORKERS worker(s) ..."
  ($PYTHON_BIN -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers "$UVICORN_WORKERS") &
  API_PID=$!

  log "Waiting for FastAPI to accept connections on 127.0.0.1:8000 ..."
  for i in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1; then
      log "FastAPI is ready."
      break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      log "ERROR: FastAPI process (PID $API_PID) exited unexpectedly during startup!"
      exit 1
    fi
    sleep 1
  done

  log "Starting Next.js frontend on 0.0.0.0:${PORT} (Node heap cap: 110MB) ..."
  (cd frontend && HOSTNAME=0.0.0.0 PORT="$PORT" NODE_OPTIONS="--max-old-space-size=110" node server.js) &
  NEXT_PID=$!

  OPENCODE_PID=""
  if [ "$ENABLE_OPENCODE_SIDECAR" = "true" ]; then
    # Brief pause to let Next.js finish its initial compilation/cache warmup
    sleep 2
    log "Starting OpenCode sidecar on 0.0.0.0:4096 (with auto-restart supervisor) ..."
    (
      while true; do
        cd /workspace 2>/dev/null || cd /app
        NODE_OPTIONS="--max-old-space-size=256" opencode serve --port 4096 --hostname 0.0.0.0 2>&1 | sed 's/^/[opencode] /' || true
        log "OpenCode sidecar exited; auto-restarting in 2s..."
        sleep 2
      done
    ) &
    OPENCODE_PID=$!
    for i in $(seq 1 15); do
      if curl -fsS http://127.0.0.1:4096/global/health >/dev/null 2>&1; then
        log "OpenCode sidecar is ready on :4096."
        break
      fi
      sleep 1
    done
  else
    log "OpenCode sidecar disabled (ENABLE_OPENCODE_SIDECAR=false) to conserve RAM."
  fi

  trap 'log "Shutting down (API=$API_PID, Next=$NEXT_PID, OpenCode=${OPENCODE_PID:-none})..."; kill $API_PID $NEXT_PID ${OPENCODE_PID:-} 2>/dev/null || true; wait' INT TERM
  wait -n "$API_PID" "$NEXT_PID" 2>/dev/null || wait
}

start_api() {
  log "Starting FastAPI API on 0.0.0.0:${PORT} with $UVICORN_WORKERS worker(s) (dedicated backend mode) ..."
  ($PYTHON_BIN -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --workers "$UVICORN_WORKERS") &
  API_PID=$!

  log "Waiting for FastAPI to accept connections on 0.0.0.0:${PORT} ..."
  for i in $(seq 1 45); do
    if curl -fsS "http://127.0.0.1:${PORT}/ready" >/dev/null 2>&1; then
      log "FastAPI is ready."
      break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      log "ERROR: FastAPI process (PID $API_PID) exited unexpectedly during startup!"
      exit 1
    fi
    sleep 1
  done

  OPENCODE_PID=""
  if [ "$ENABLE_OPENCODE_SIDECAR" = "true" ]; then
    log "Starting OpenCode sidecar on 0.0.0.0:4096 (with auto-restart supervisor) ..."
    (
      while true; do
        cd /workspace 2>/dev/null || cd /app
        NODE_OPTIONS="--max-old-space-size=256" opencode serve --port 4096 --hostname 0.0.0.0 2>&1 | sed 's/^/[opencode] /' || true
        log "OpenCode sidecar exited; auto-restarting in 2s..."
        sleep 2
      done
    ) &
    OPENCODE_PID=$!
    for i in $(seq 1 15); do
      if curl -fsS http://127.0.0.1:4096/global/health >/dev/null 2>&1; then
        log "OpenCode sidecar is ready on :4096."
        break
      fi
      sleep 1
    done
  else
    log "OpenCode sidecar disabled (ENABLE_OPENCODE_SIDECAR=false) to conserve RAM."
  fi

  trap 'log "Shutting down (API=$API_PID, OpenCode=${OPENCODE_PID:-none})..."; kill $API_PID ${OPENCODE_PID:-} 2>/dev/null || true; wait' INT TERM
  wait -n "$API_PID" 2>/dev/null || wait
}

start_builder() {
  log "Starting opencode serve on 0.0.0.0:4096 ..."
  (cd /workspace && opencode serve --port 4096 --hostname 0.0.0.0) &
  OPENCODE_PID=$!

  log "Starting background build worker ..."
  (cd /app && $PYTHON_BIN -m app.worker) &
  WORKER_PID=$!

  trap 'log "Shutting down (opencode=$OPENCODE_PID, worker=$WORKER_PID)..."; kill $OPENCODE_PID $WORKER_PID 2>/dev/null || true; wait' INT TERM
  wait
}

start_worker_only() {
  log "Starting background build worker (legacy mode) ..."
  exec $PYTHON_BIN -m app.worker
}

# Machine workdir is /app inside containers; docker-compose runs this from the
# backend directory so it stays as the migration/uvicorn cwd.
APP_DIR="/app"; [ -d "/app/app" ] || APP_DIR="$PWD"

run_migrations "$APP_DIR"

case "$ROLE" in
  app)
    if [ "${DISABLE_FRONTEND:-false}" = "true" ]; then
      log "DISABLE_FRONTEND=true: running in dedicated API mode."
      start_api
    else
      start_app
    fi
    ;;
  api|backend)
    start_api
    ;;
  builder)
    start_builder
    ;;
  worker)
    start_worker_only
    ;;
  *)
    echo "[entrypoint] Unknown role '$ROLE' (expected app|api|backend|builder|worker)" >&2
    exit 2
    ;;
esac