#!/usr/bin/env bash
# AI Solution Builder — Unified Local Stack Runner
#
# Runs the entire application locally with ZERO Docker bloat on your C: drive,
# or optionally with lightweight Docker infra (Postgres+Redis only) or full Docker.
#
# Modes & Usage:
#   ./run_local.sh              (DEFAULT) Run entire stack locally WITHOUT Docker (0 C-drive bloat)
#   ./run_local.sh -d           Run native stack detached in background
#   ./run_local.sh native       Explicitly run native stack without Docker
#   ./run_local.sh infra        Lightweight Docker: run Postgres+Redis in Docker, app native
#   ./run_local.sh docker       Run entire stack in Docker (no forced rebuilds)
#   ./run_local.sh docker --build Run full Docker stack with forced image rebuilds
#   ./run_local.sh stop         Stop all running services (native and/or docker)
#   ./run_local.sh status       Show health, process, and port status
#   ./run_local.sh logs [svc]   Tail logs (backend, frontend, opencode, worker)
#   ./run_local.sh prune        Reclaim GBs on C: drive (prune Docker build cache & images)
#   ./run_local.sh down         Stop services and remove containers/volumes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Resolve absolute repo root (Windows-friendly if running under Git Bash / MSYS)
REPO_ROOT="$(pwd -W 2>/dev/null || pwd)"

BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:3000"
SIDECAR_URL="http://127.0.0.1:4096"
HEALTH_TIMEOUT=90

LOG_DIR="$SCRIPT_DIR/.data/logs"
PID_DIR="$SCRIPT_DIR/.data/pids"
DATA_DIR="$SCRIPT_DIR/.data"

mkdir -p "$LOG_DIR" "$PID_DIR" "$DATA_DIR/mvp_builds" "$DATA_DIR/uploads" "$DATA_DIR/exports"

# ANSI Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log()   { printf "\n${CYAN}==> %s${NC}\n" "$*"; }
info()  { printf "    ${GREEN}✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}WARNING: %s${NC}\n" "$*" >&2; }
err()   { printf "${RED}ERROR: %s${NC}\n" "$*" >&2; }
die()   { err "$*"; exit 1; }

# ── Helper: Docker Compose binary ─────────────────────────────────────────────
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose not found. Please install Docker Desktop or run in native mode."
  fi
}

# ── Helper: Find Python Interpreter ───────────────────────────────────────────
find_python() {
  if [ -f "$SCRIPT_DIR/backend/.venv/Scripts/python.exe" ]; then
    echo "$SCRIPT_DIR/backend/.venv/Scripts/python.exe"
  elif [ -f "$SCRIPT_DIR/backend/.venv/bin/python" ]; then
    echo "$SCRIPT_DIR/backend/.venv/bin/python"
  elif [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    echo "$SCRIPT_DIR/.venv/Scripts/python.exe"
  elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    echo "$SCRIPT_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    echo ""
  fi
}

# ── Helper: Environment File ──────────────────────────────────────────────────
ensure_env() {
  if [ ! -f .env ]; then
    log "Creating .env from .env.example"
    cp .env.example .env
    warn ".env was created from template. Fill in API keys if needed."
  fi
}

# ── Helper: Check URL listening ───────────────────────────────────────────────
check_url() {
  local url="$1"
  curl -fsS -o /dev/null -m 2 "$url" 2>/dev/null
}

# ── Helper: Check TCP Port listening ──────────────────────────────────────────
check_port() {
  local port="$1"
  if command -v netstat.exe >/dev/null 2>&1; then
    netstat.exe -ano | grep -E "LISTENING.*:${port}\b|:${port}\b.*LISTENING" >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -tlpn | grep -q ":${port} "
  else
    nc -z 127.0.0.1 "$port" 2>/dev/null || (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null
  fi
}

# ── Helper: Free Port if occupied ─────────────────────────────────────────────
free_port() {
  local port="$1"
  if check_port "$port"; then
    warn "Port $port is in use. Attempting to free..."
    if command -v netstat.exe >/dev/null 2>&1 && command -v taskkill >/dev/null 2>&1; then
      local pids
      pids="$(netstat.exe -ano | grep -E "LISTENING.*:${port}\b|:${port}\b.*LISTENING" | awk '{print $NF}' | sort -u || true)"
      for p in $pids; do
        if [ "$p" != "0" ] && [ -n "$p" ]; then
          taskkill //F //T //PID "$p" >/dev/null 2>&1 || true
        fi
      done
    elif command -v fuser >/dev/null 2>&1; then
      fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    fi
    sleep 0.5
  fi
}

# ── Helper: Kill PID safely ───────────────────────────────────────────────────
kill_pid() {
  local pid="$1"
  [ -z "$pid" ] && return 0
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
  sleep 0.5
  kill -9 "$pid" 2>/dev/null || true
}

stop_pid_file() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ]; then
      printf "  Stopping %-18s (PID %s)... " "$name" "$pid"
      kill_pid "$pid"
      echo "done"
    fi
    rm -f "$pid_file"
  fi
}

# ── Helper: Wait for service health ───────────────────────────────────────────
wait_for() {
  local name="$1" url="$2" timeout="$3" logfile="${4:-}"
  local elapsed=0
  printf '  Waiting for %-26s' "$name"
  while [ "$elapsed" -lt "$timeout" ]; do
    if check_url "$url"; then
      echo -e "${GREEN} OK${NC} ($url)"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo -e "${RED} TIMEOUT${NC} ($url)"
  if [ -n "$logfile" ] && [ -f "$logfile" ]; then
    echo -e "${YELLOW}--- Last 15 lines of $logfile ---${NC}"
    tail -n 15 "$logfile" 2>/dev/null || true
    echo -e "${YELLOW}---------------------------------${NC}"
  fi
  return 1
}

# ── Stop All Services ─────────────────────────────────────────────────────────
stop_all() {
  log "Stopping all local services"
  stop_pid_file "frontend"
  stop_pid_file "backend"
  stop_pid_file "worker"
  stop_pid_file "opencode"

  # Also stop any running docker containers from this project
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if [ -f docker-compose.yml ]; then
      printf "  Stopping Docker containers... "
      compose stop >/dev/null 2>&1 || true
      echo "done"
    fi
  fi
  info "All services stopped."
}

# ── Status ────────────────────────────────────────────────────────────────────
show_status() {
  log "AI Solution Builder Service Status"

  check_svc() {
    local name="$1" port="$2" url="$3" pidfile="$PID_DIR/$1.pid"
    local pid="" status="${RED}STOPPED${NC}"
    if [ -f "$pidfile" ]; then
      pid="$(cat "$pidfile" 2>/dev/null || true)"
    fi

    if [ "$name" = "worker" ]; then
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        status="${GREEN}RUNNING (PID $pid)${NC}"
      else
        status="${YELLOW}STOPPED / INLINE${NC}"
      fi
    elif [ "$port" != "-" ] && check_port "$port"; then
      if [ -n "$url" ] && (check_url "$url" || check_url "$url/api/info" || check_url "$url/global/health"); then
        status="${GREEN}HEALTHY (HTTP 200)${NC}"
      else
        status="${YELLOW}LISTENING (port $port)${NC}"
      fi
    else
      status="${RED}STOPPED${NC}"
    fi

    printf "  %-14s Port: %-6s PID: %-8s Status: %b\n" "$name" "$port" "${pid:--}" "$status"
  }

  check_svc "backend"  "8000" "$BACKEND_URL/health"
  check_svc "frontend" "3000" "$FRONTEND_URL"
  check_svc "opencode" "4096" "$SIDECAR_URL"
  check_svc "worker"   "-"    ""

  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo ""
    printf "  ${BOLD}Docker containers:${NC}\n"
    compose ps 2>/dev/null || echo "    No docker compose containers active"
  fi
}

# ── Tail Logs ─────────────────────────────────────────────────────────────────
tail_logs() {
  local target="${1:-all}"
  log "Streaming logs for: $target (Press Ctrl+C to stop)"
  case "$target" in
    backend)
      [ -f "$LOG_DIR/backend.log" ] && tail -f "$LOG_DIR/backend.log" || warn "backend.log not found"
      ;;
    frontend)
      [ -f "$LOG_DIR/frontend.log" ] && tail -f "$LOG_DIR/frontend.log" || warn "frontend.log not found"
      ;;
    opencode)
      [ -f "$LOG_DIR/opencode.log" ] && tail -f "$LOG_DIR/opencode.log" || warn "opencode.log not found"
      ;;
    worker)
      [ -f "$LOG_DIR/worker.log" ] && tail -f "$LOG_DIR/worker.log" || warn "worker.log not found"
      ;;
    docker)
      compose logs -f --tail=50
      ;;
    all|*)
      # Tail all existing log files
      local files=()
      for f in "$LOG_DIR"/*.log; do
        [ -f "$f" ] && files+=("$f")
      done
      if [ ${#files[@]} -gt 0 ]; then
        tail -f "${files[@]}"
      else
        warn "No log files found in $LOG_DIR yet."
      fi
      ;;
  esac
}

# ── Prune Docker Bloat (Reclaim C: Drive Space) ────────────────────────────────
prune_docker() {
  log "Reclaiming C: drive space from Docker Desktop"
  command -v docker >/dev/null 2>&1 || die "docker command not found."
  docker info >/dev/null 2>&1 || die "Docker daemon is not running."

  echo "Current Docker disk usage:"
  docker system df

  log "1. Stopping and removing any stopped AI Solution Builder containers..."
  compose stop 2>/dev/null || true
  compose rm -f 2>/dev/null || true
  docker container prune -f >/dev/null 2>&1 || true

  log "2. Pruning dangling Docker build cache (BuildKit layers on C: drive)..."
  docker builder prune -f

  log "3. Pruning dangling images..."
  docker image prune -f

  log "4. Removing large custom built images for AI Solution Builder..."
  docker rmi ai_solution_builder-backend ai_solution_builder-worker ai_solution_builder-opencode ai_solution_builder-frontend 2>/dev/null || true

  echo ""
  log "Docker disk usage after cleanup:"
  docker system df
  info "Docker cleanup complete. Your C: drive has reclaimed space."
}

# ── Start Native Stack (Zero Docker) ──────────────────────────────────────────
start_native() {
  local detach="${1:-false}"
  ensure_env

  log "Checking prerequisites for Native Mode (No Docker)"

  PYTHON_BIN="$(find_python)"
  [ -z "$PYTHON_BIN" ] && die "Python not found. Please install Python 3.12+ or create backend/.venv"
  command -v node >/dev/null 2>&1 || die "Node.js not found. Please install Node.js 20+"
  command -v npm >/dev/null 2>&1 || die "npm not found. Please install npm"

  info "Python:   $("$PYTHON_BIN" --version 2>&1) ($PYTHON_BIN)"
  info "Node.js:  $(node --version) ($(command -v node))"
  info "npm:      $(npm --version)"

  # Check OpenCode CLI
  OPENCODE_BIN=""
  if command -v opencode >/dev/null 2>&1; then
    OPENCODE_BIN="opencode"
    info "OpenCode: $(opencode --version 2>/dev/null || echo 'installed') ($(command -v opencode))"
  else
    warn "opencode CLI not found in PATH. Install with: npm i -g opencode"
    warn "MVP build features will fall back to mocked/external provider."
  fi

  # Check frontend node_modules
  if [ ! -d "frontend/node_modules" ]; then
    log "Installing frontend dependencies (npm install in frontend/)..."
    (cd frontend && npm install)
  fi

  # Free ports if leftover processes exist
  free_port 8000
  free_port 3000

  # 1. Start OpenCode Sidecar on port 4096
  log "Starting OpenCode sidecar on port 4096"
  if check_url "$SIDECAR_URL/api/info" || check_url "$SIDECAR_URL/global/health" || check_port 4096; then
    info "OpenCode sidecar already running on port 4096 — reusing existing instance."
  elif [ -n "$OPENCODE_BIN" ]; then
    # Seed Zen credentials if present in .env and auth.json doesn't exist
    local zen_key
    zen_key="$(grep -E '^OPENCODE_ZEN_API_KEY=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"'\'' ' || true)"
    if [ -n "$zen_key" ]; then
      local auth_dir="${HOME}/.local/share/opencode"
      mkdir -p "$auth_dir"
      if [ ! -f "$auth_dir/auth.json" ]; then
        cat > "$auth_dir/auth.json" <<EOF
{
  "opencode": {
    "type": "api",
    "key": "${zen_key}"
  }
}
EOF
      fi
    fi

    cd "$SCRIPT_DIR/backend/opencode"
    nohup opencode serve --port 4096 --hostname 127.0.0.1 </dev/null > "$LOG_DIR/opencode.log" 2>&1 &
    local oc_pid=$!
    echo "$oc_pid" > "$PID_DIR/opencode.pid"
    disown "$oc_pid" 2>/dev/null || true
    cd "$SCRIPT_DIR"
    info "OpenCode sidecar started (PID $oc_pid)"
  fi

  # 2. Start Backend FastAPI on port 8000
  log "Starting FastAPI Backend API on port 8000"
  cd "$SCRIPT_DIR/backend"
  export MVP_BUILD_DIR="$DATA_DIR/mvp_builds"
  nohup "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port 8000 </dev/null > "$LOG_DIR/backend.log" 2>&1 &
  local bk_pid=$!
  echo "$bk_pid" > "$PID_DIR/backend.pid"
  disown "$bk_pid" 2>/dev/null || true
  cd "$SCRIPT_DIR"
  info "Backend started (PID $bk_pid)"

  # 3. Start Background Worker (if WORKER_MODE=worker)
  local worker_mode
  worker_mode="$(grep -E '^WORKER_MODE=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"'\'' ' || echo 'inline')"
  if [ "$worker_mode" = "worker" ]; then
    log "Starting Build Worker process (WORKER_MODE=worker)"
    cd "$SCRIPT_DIR/backend"
    export MVP_BUILD_DIR="$DATA_DIR/mvp_builds"
    nohup "$PYTHON_BIN" -m app.worker </dev/null > "$LOG_DIR/worker.log" 2>&1 &
    local wk_pid=$!
    echo "$wk_pid" > "$PID_DIR/worker.pid"
    disown "$wk_pid" 2>/dev/null || true
    cd "$SCRIPT_DIR"
    info "Worker process started (PID $wk_pid)"
  else
    info "Worker mode: inline (builds execute in-process inside FastAPI)"
  fi

  # 4. Start Frontend Next.js dev server on port 3000
  log "Starting Next.js Frontend on port 3000"
  cd "$SCRIPT_DIR/frontend"
  nohup npm run dev -- --port 3000 </dev/null > "$LOG_DIR/frontend.log" 2>&1 &
  local fe_pid=$!
  echo "$fe_pid" > "$PID_DIR/frontend.pid"
  disown "$fe_pid" 2>/dev/null || true
  cd "$SCRIPT_DIR"
  info "Frontend started (PID $fe_pid)"

  # 5. Wait for services to become healthy
  log "Waiting for services to become healthy (timeout: ${HEALTH_TIMEOUT}s)"
  local failed=0
  wait_for "Backend /health"   "$BACKEND_URL/health" "$HEALTH_TIMEOUT" "$LOG_DIR/backend.log"  || failed=1
  wait_for "Backend /ready"    "$BACKEND_URL/ready"  "$HEALTH_TIMEOUT" "$LOG_DIR/backend.log"  || failed=1
  wait_for "Frontend"          "$FRONTEND_URL"       "$HEALTH_TIMEOUT" "$LOG_DIR/frontend.log" || failed=1
  if [ -n "$OPENCODE_BIN" ]; then
    wait_for "OpenCode Sidecar" "$SIDECAR_URL"        30                "$LOG_DIR/opencode.log" || true
  fi

  if [ "$failed" -ne 0 ]; then
    warn "One or more services did not become ready within timeout."
    warn "Check logs with: ./run_local.sh logs"
  else
    log "${GREEN}All services are up and healthy!${NC}"
  fi

  cat <<EOF

  ${BOLD}AI Solution Builder is running locally (Zero Docker / Native Mode)${NC}

  ➜ ${BOLD}Frontend:${NC}        ${CYAN}$FRONTEND_URL${NC}
  ➜ ${BOLD}Backend API:${NC}     ${CYAN}$BACKEND_URL${NC}
  ➜ ${BOLD}Interactive Docs:${NC}${CYAN}$BACKEND_URL/docs${NC}
  ➜ ${BOLD}Health Probes:${NC}   $BACKEND_URL/health  |  $BACKEND_URL/ready
  ➜ ${BOLD}OpenCode Sidecar:${NC}$SIDECAR_URL

  ${BOLD}Useful Commands:${NC}
    ./run_local.sh status     Check status of all services
    ./run_local.sh logs       Tail all service logs
    ./run_local.sh stop       Stop all services
    ./run_local.sh prune      Clean Docker build cache & reclaim C: drive

EOF

  if [ "$detach" = "true" ]; then
    info "Running in detached background mode. Use './run_local.sh logs' to monitor."
    exit 0
  fi

  # Foreground mode: trap Ctrl+C and stop cleanly
  cleanup() {
    printf "\n"
    stop_all
    exit 0
  }
  trap cleanup INT TERM

  info "Tailing service logs. Press Ctrl+C at any time to shut down the stack."
  echo ""
  tail_logs all
}

# ── Start Infra Only (Lightweight Postgres + Redis in Docker, App Native) ─────
start_infra() {
  ensure_env
  log "Starting lightweight Docker infrastructure (Postgres + Redis only — no custom builds)"
  command -v docker >/dev/null 2>&1 || die "docker not found. Start Docker Desktop or use native mode."
  docker info >/dev/null 2>&1 || die "Docker daemon not running. Start Docker Desktop and retry."

  compose up -d postgres redis
  info "Postgres (port 5433->5432) and Redis (port 6379) are running in Docker."
  info "Now starting application surfaces natively on host (0 build bloat)..."
  start_native "false"
}

# ── Start Full Docker Stack ───────────────────────────────────────────────────
start_docker() {
  local rebuild="${1:-false}"
  ensure_env
  log "Starting stack with Docker Compose"
  command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker Desktop."
  docker info >/dev/null 2>&1 || die "Docker daemon is not running."

  if [ "$rebuild" = "true" ]; then
    warn "Rebuilding Docker images (--build). Note: this may consume disk on C: drive."
    compose up --build -d
  else
    info "Starting existing containers without rebuilding (saves C: drive space)..."
    compose up -d
  fi

  log "Waiting for services..."
  wait_for "Backend /ready"   "$BACKEND_URL/ready"  "$HEALTH_TIMEOUT" || true
  wait_for "Frontend"         "$FRONTEND_URL"       "$HEALTH_TIMEOUT" || true
  wait_for "OpenCode sidecar" "$SIDECAR_URL/api/info" 30 || true

  cat <<EOF

  Docker Stack is running:
  Frontend:    $FRONTEND_URL
  Backend:     $BACKEND_URL
  Docs:        $BACKEND_URL/docs
  Sidecar:     $SIDECAR_URL

  Commands:
    ./run_local.sh stop    Stop containers
    ./run_local.sh logs    Tail logs
    ./run_local.sh prune   Clean Docker build cache & reclaim C: drive

EOF
}

# ── CLI Router ────────────────────────────────────────────────────────────────
COMMAND="${1:-up}"
if [[ "$COMMAND" == -* ]]; then
  COMMAND="up"
else
  shift || true
fi

case "$COMMAND" in
  up|start|native|local)
    # Check if -d or --detach is passed
    DETACH="false"
    for arg in "$@" ""; do
      if [ "$arg" = "-d" ] || [ "$arg" = "--detach" ] || [ "$arg" = "--background" ]; then
        DETACH="true"
      elif [ "$arg" = "--docker" ]; then
        start_docker "false"
        exit 0
      fi
    done
    start_native "$DETACH"
    ;;
  infra|docker-infra)
    start_infra
    ;;
  docker)
    REBUILD="false"
    for arg in "$@" ""; do
      if [ "$arg" = "--build" ]; then
        REBUILD="true"
      fi
    done
    start_docker "$REBUILD"
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    sleep 2
    start_native "false"
    ;;
  status|ps)
    show_status
    ;;
  logs)
    tail_logs "${1:-all}"
    ;;
  prune|clean|clean-docker)
    prune_docker
    ;;
  down)
    stop_all
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
      log "Removing Docker containers and volumes (DATA WILL BE DELETED)"
      compose down -v 2>/dev/null || true
    fi
    info "Down complete."
    ;;
  help|--help|-h)
    cat <<EOF
Usage: $0 [COMMAND] [OPTIONS]

Run the AI Solution Builder stack locally.

Commands:
  (no args)             (Default) Run entire stack locally WITHOUT Docker (0 C: drive bloat)
  up, native, local     Run native stack on host (backend + frontend + opencode + worker)
  up -d                 Run native stack in detached background mode
  infra                 Lightweight mode: run Postgres+Redis in Docker, app natively
  docker                Run entire stack in Docker (no forced rebuilds)
  docker --build        Run full Docker stack and rebuild images
  stop                  Stop all running services (native and/or Docker)
  restart               Stop and restart the native stack
  status, ps            Display health and process status
  logs [service]        Tail logs (all, backend, frontend, opencode, worker, docker)
  prune, clean          Clean Docker build cache & unused images to reclaim C: drive space
  down                  Stop all services and remove Docker volumes

EOF
    ;;
  *)
    err "Unknown command: $COMMAND"
    echo "Run '$0 help' for available commands." >&2
    exit 1
    ;;
esac
