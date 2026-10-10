#!/usr/bin/env bash
# AI Solution Builder — OpenCode sidecar entrypoint
#
# Responsibilities:
#   1. Work out of the box with Free-tier models: the default generation model
#      is `opencode/step-5-preview-free` and the default cheap model (titles,
#      summaries) is `opencode/nemotron-3.5-lightning-free`, both free via
#      OpenCode Zen. Set OPENCODE_ZEN_API_KEY for them; without it, override
#      OPENCODE_MODEL to a groq/* model and supply GROQ_API_KEY instead.
#      Neither OPENCODE_SERVER_PASSWORD nor a Zen key is required to boot.
#   2. Seed the OpenCode Zen credential file (~/.local/share/opencode/auth.json)
#      ONLY when OPENCODE_ZEN_API_KEY is set.
#   3. Print a startup diagnostics banner for `docker logs`/`render logs`.
#   4. serve `opencode` with stdout/stderr prefixed by `[opencode] ` so it
#      is grep-able alongside the backend's own log stream.

set -euo pipefail

log() { echo "[opencode] $*"; }

# The config is baked into the image so it remains reviewable, but the selected
# models are deployment configuration. Resolve the explicit placeholders at
# startup rather than silently ignoring OPENCODE_MODEL / OPENCODE_SMALL_MODEL.
MODEL="${OPENCODE_MODEL:-opencode/step-5-preview-free}"
SMALL_MODEL="${OPENCODE_SMALL_MODEL:-opencode/nemotron-3.5-lightning-free}"
for VALUE in "${MODEL}" "${SMALL_MODEL}"; do
  if ! printf '%s' "${VALUE}" | grep -Eq '^[A-Za-z0-9._/:@-]+$'; then
    log "fatal: model name '${VALUE}' contains unsupported characters"
    exit 64
  fi
done
CONFIG_FILE="${HOME}/.config/opencode/opencode.json"
if [ ! -f "${CONFIG_FILE}" ]; then
  log "fatal: OpenCode configuration is missing at ${CONFIG_FILE}"
  exit 78
fi
sed -i "s|__OPENCODE_MODEL__|${MODEL}|g" "${CONFIG_FILE}"
sed -i "s|__OPENCODE_SMALL_MODEL__|${SMALL_MODEL}|g" "${CONFIG_FILE}"

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
log "diag: starting opencode serve (model=${MODEL}, small_model=${SMALL_MODEL}, agent=${OPENCODE_AGENT:-mvp-builder})"
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
