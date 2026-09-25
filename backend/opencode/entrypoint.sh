#!/usr/bin/env bash
# AI Solution Builder — OpenCode sidecar entrypoint
#
# Responsibilities:
#   1. Fail fast (non-zero exit) when OPENCODE_ZEN_API_KEY is missing, so the
#      container never silently half-starts and crash-loops invisibly.
#   2. Seed the OpenCode Zen credential file (~/.local/share/opencode/auth.json)
#      so every LLM call is authenticated out of the box.
#   3. Print a startup diagnostics banner for `docker logs`/`render logs`.
#   4. serve `opencode` with stdout/stderr prefixed by `[opencode] ` so it
#      is grep-able alongside the backend's own log stream.

set -euo pipefail

log() { echo "[opencode] $*"; }

# ── 1. Fail fast on missing Zen key ──────────────────────────────────────
if [ -z "${OPENCODE_ZEN_API_KEY:-}" ]; then
  echo "[opencode] FATAL: OPENCODE_ZEN_API_KEY is not set." >&2
  echo "[opencode] FATAL: Set it, e.g.: export OPENCODE_ZEN_API_KEY=<your-zen-key>" >&2
  # Exit non-zero so Docker/Render surface the failure instead of a half-start.
  exit 1
fi

# ── 2. Seed Zen credentials ──────────────────────────────────────────────
# OpenCode reads provider credentials from ~/.local/share/opencode/auth.json.
# The Zen provider id is "opencode" with an api-key secret.
AUTH_DIR="${HOME}/.local/share/opencode"
AUTH_FILE="${AUTH_DIR}/auth.json"
mkdir -p "${AUTH_DIR}"
umask 077
cat > "${AUTH_FILE}" <<EOF
{
  "opencode": {
    "type": "api",
    "key": "${OPENCODE_ZEN_API_KEY}"
  }
}
EOF
chmod 600 "${AUTH_FILE}"

# ── 3. Diagnostics banner ────────────────────────────────────────────────
log "diag: starting opencode serve (model=${OPENCODE_MODEL:-opencode/big-pickle}, agent=${OPENCODE_AGENT:-mvp-builder})"
log "diag: auth file present: $([ -f "${AUTH_FILE}" ] && echo yes || echo no)"
log "diag: node: $(node --version 2>/dev/null || echo missing)"
log "diag: python3: $(python3 --version 2>&1 || echo missing)"
log "diag: git: $(git --version 2>/dev/null || echo missing)"
log "diag: ripgrep: $(rg --version 2>/dev/null | head -n1 || echo missing)"
log "diag: bash: $([ -x /bin/bash ] && echo present || echo missing)"

# ── 4. Serve (prefixed, signal-forwarding; PID 1 stays bash) ──────────────
opencode serve --port 4096 --hostname 0.0.0.0 2>&1 | sed 's/^/[opencode] /' &
SERVE_PID=$!
trap 'log "shutdown signal received; stopping opencode (pid ${SERVE_PID})"; kill -TERM "${SERVE_PID}" 2>/dev/null || true' INT TERM
wait "${SERVE_PID}"
log "opencode serve exited (code $?)"