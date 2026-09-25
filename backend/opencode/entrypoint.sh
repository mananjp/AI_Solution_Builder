#!/usr/bin/env bash
# AI Solution Builder — OpenCode sidecar entrypoint
#
# Responsibilities:
#   1. Work out of the box: the default model is `opencode/big-pickle` (OpenCode
#      Zen). Set OPENCODE_ZEN_API_KEY for it; without it, generation degrades to
#      the GROQ_API_KEY fallback (groq/* model) if you override OPENCODE_MODEL.
#      Neither OPENCODE_SERVER_PASSWORD nor a Zen key is required to boot.
#   2. Seed the OpenCode Zen credential file (~/.local/share/opencode/auth.json)
#      ONLY when OPENCODE_ZEN_API_KEY is set.
#   3. Print a startup diagnostics banner for `docker logs`/`render logs`.
#   4. serve `opencode` with stdout/stderr prefixed by `[opencode] ` so it
#      is grep-able alongside the backend's own log stream.

set -euo pipefail

log() { echo "[opencode] $*"; }

# ── 1. Optional Zen credentials ──────────────────────────────────────────
# OpenCode reads provider credentials from ~/.local/share/opencode/auth.json.
# The Zen provider id is "opencode" with an api-key secret. Skip when unset —
# Groq (GROQ_API_KEY from config.json provider block) works without it.
AUTH_DIR="${HOME}/.local/share/opencode"
AUTH_FILE="${AUTH_DIR}/auth.json"
if [ -n "${OPENCODE_ZEN_API_KEY:-}" ]; then
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
  log "diag: zen credentials seeded"
else
  log "diag: OPENCODE_ZEN_API_KEY unset — set it (https://opencode.ai/zen) or override OPENCODE_MODEL with a groq/* model"
fi

# ── 2. Diagnostics banner ────────────────────────────────────────────────
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