# Feature Ticket: Fix OpenCode Sidecar & Full Agent Observability

**Ticket ID:** `FEAT-OPENCODE-002`
**Status:** Approved / Ready to Implement
**Component:** Backend (`backend/opencode/`, `app/api/opencode_chat.py`, `app/services/mvp_builder.py`, `app/services/opencode_logger.py`), Frontend (chat/dashboard), Infra (`docker-compose.yml`, `fly.toml`, `render.yaml`)
**Priority:** High (Production Blocking)

---

## 1. Problem Statement

The OpenCode sidecar container (`opencode serve`, port 4096) is not working: MVP builds silently fall back to the integrated synthesizer and the agent never generates code. Additionally there is **zero observability** — agent activity, tool calls, test runs, and provider errors exist only in throwaway container stdout, so a broken sidecar is invisible until a build ships broken.

### 1.1 Root Causes Identified

1. **Invalid env interpolation in `config.json`.** OpenCode supports only `{env:VAR}` (unset → empty string) — *not* `{env:VAR:-default}`. Both `backend/opencode/config.json:3` and `:13` use `{env:OPENCODE_MODEL:-opencode/big-pickle}`. When `OPENCODE_MODEL` is unset inside the container (docker-compose never passes it), the top-level `model` resolves to an empty/garbage string and `opencode serve` fails to start → crash loop.
2. **Agent model hardcodes OpenCode Zen.** `backend/opencode/agents/mvp-builder.md:4` sets `model: opencode/big-pickle`, a Zen model requiring an API key in `~/.local/share/opencode/auth.json`. The container has no key → every LLM call 401s even when serve is up.
3. **Inconsistent model wiring.** `backend/app/core/config.py:112` defaults to `opencode/big-pickle`; `.env.example:45` documents `groq/...`; `fly.toml:29` and `README.md:362` use Zen; `docker-compose.yml:107-119` passes only `GROQ_*` vars. No single source of truth, and neither `OPENCODE_MODEL` nor any Zen credential is propagated to the sidecar.
4. **Sidecar image missing runtime tools.** `backend/opencode/Dockerfile:4` builds on `node:20-slim` with no `git`, no `ripgrep`, no `bash` → opencode's grep/VCS/project tools and the agent's `pytest`/`npm` commands cannot run reliably.
5. **No failure signal.** `builder.health()` only probes `/global/health` (server process up), so `GET /api/v1/opencode/health` reports `healthy: True` while generation is broken. Provider errors at `mvp_builder.py:2494` are logged to stdout and swallowed.

### 1.2 Decisions (Confirmed)

- **Provider:** OpenCode Zen (`opencode/big-pickle`, free tier) — requires `OPENCODE_ZEN_API_KEY`.
- **Log persistence:** Cloudinary (object storage) via existing `app/services/storage.py`, with a thin Postgres lookup index.

---

## 2. Existing Assets & Architecture

### A. Sidecar image
- `backend/opencode/Dockerfile` — node:20-slim, pip preinstalls MVP runtime deps, `npm i -g @opencode/cli@latest`, healthcheck hits `/global/health`.
- `backend/opencode/config.json` — model via broken `{env:...:-...}` syntax, `groq` provider block.
- `backend/opencode/agents/mvp-builder.md` — custom primary agent, `permission` allow list, hardcoded `model: opencode/big-pickle`.
- `docker-compose.yml:107-119` — opencode service: Groq env only, shares `mvp_workspace:/workspace`.
- `backend/entrypoint.sh:68,113,136` — `opencode serve` piped to stdout with `[opencode]` prefix.

### B. Backend integration
- `backend/app/services/mvp_builder.py` — `update:health()`, `create_session()`, `send_message()` (HTTP proxy to sidecar), `run_build()` at `:2450-2530`, `_auth_headers()` (basic auth `opencode:<password>`), `_candidate_urls()`.
- `backend/app/api/opencode_chat.py` — SSE `/opencode/chat`, `/opencode/health`; events `agent_start | build_progress | message | complete | error`.
- `backend/app/models/mvp_build.py` — stores `opencode_session_id`, `storage_key`, `error_message`.
- `backend/app/services/storage.py` — `StorageBackend` ABC, `LocalStorage`, `CloudinaryStorage`, `get_storage()` factory (Cloudinary `raw` uploads via `cloudinary.uploader`).

### C. OpenCode server API (verified against v1.18.x docs)
- `GET /global/health` → `{ healthy, version }`
- `GET /event` → global SSE bus (first event `server.connected`)
- `GET /global/event` → SSE stream too
- `GET /config`, `GET /provider` → active model, providers, `connected: string[]`
- `POST /session`, `POST /session/{id}/message`, `POST /session/{id}/abort`
- `GET /session/{id}/message` → full transcript (fallback logger)
- `PUT /auth/:id` → set provider credentials (Zen = provider id `opencode`)
- Zen credentials normally stored in `~/.local/share/opencode/auth.json` via `/connect`.

---

## 3. Implementation Plan

### Phase 1 — Make the Sidecar Work (OpenCode Zen)

#### 1.1 `backend/opencode/Dockerfile`
- Pin the CLI: `npm install -g @opencode/cli@1.18.31` (matches `opencode-ai@1.18.31` in `app.Dockerfile`; removes `@latest` drift).
- Install runtime tools: `apt-get install -y --no-install-recommends git ripgrep bash curl jq ca-certificates procps`.
- Add `COPY entrypoint.sh /opt/opencode/entrypoint.sh` + `ENTRYPOINT`; keep `CMD ["opencode","serve","--port","4096","--hostname","0.0.0.0"]`.

#### 1.2 `backend/opencode/entrypoint.sh` (new)
1. Fail fast if `OPENCODE_ZEN_API_KEY` missing → print `[opencode] FATAL: OPENCODE_ZEN_API_KEY is not set...` and exit non-zero (visible in `docker logs`, container won't silently half-start).
2. Write Zen credential file:
   ```json
   { "opencode": { "type": "api", "key": "$OPENCODE_ZEN_API_KEY" } }
   ```
   → `~/.local/share/opencode/auth.json` (chmod 600). Fallback: after serve starts, call `PUT /auth/opencode` with the key (both paths validated live during implementation).
3. Print startup diagnostics banner: resolved model, agent, node/python/git/rg versions, auth file presence (`[opencode] diag: ...`).
4. `exec opencode serve --port 4096 --hostname 0.0.0.0` (2>&1 piped to a `sed 's/^/[opencode] /'` line prefix like `backend/entrypoint.sh` for grep-ability).

#### 1.3 `backend/opencode/config.json`
- Replace broken interpolation with plain values:
  ```json
  { "$schema": "https://opencode.ai/config.json",
    "model": "opencode/big-pickle",
    "small_model": "opencode/big-pickle",
    "agent": { "mvp-builder": { "description": "...", "mode": "primary" } } }
  ```
- Keep provider block for possible Groq fallback but move key under `options.apiKey` (flat `apiKey` is ignored per docs):
  ```json
  "provider": { "groq": { "options": { "apiKey": "{env:GROQ_API_KEY}" } } }
  ```
- Remove the malformed `{env:OPENCODE_MODEL:-...}` tokens.

#### 1.4 `backend/opencode/agents/mvp-builder.md`
- Keep `model: opencode/big-pickle`. No removal — it is now correct and consistent with config.json. (Verified honored during implementation.)

#### 1.5 `docker-compose.yml` (opencode service)
- Add env:
  ```yaml
  OPENCODE_ZEN_API_KEY: ${OPENCODE_ZEN_API_KEY:-}
  OPENCODE_MODEL: ${OPENCODE_MODEL:-opencode/big-pickle}
  OPENCODE_AGENT: ${OPENCODE_AGENT:-mvp-builder}
  ```
- Keep `OPENCODE_SERVER_PASSWORD`, `GROQ_*`, `/workspace` volume, healthcheck.

#### 1.6 Config consistency
- `backend/app/core/config.py`: `OPENCODE_ZEN_API_KEY: str = ""`; `OPENCODE_MODEL: str = "opencode/big-pickle"`; `OPENCODE_AGENT: str = "mvp-builder"` already present.
- `fly.toml`: add `OPENCODE_ZEN_API_KEY` (secret) + set `OPENCODE_MODEL = "opencode/big-pickle"`.
- `render.yaml`: add `OPENCODE_ZEN_API_KEY` to sidecar env blocks (`:53-59`, `:136-138`).
- `.env.example:45`: correct comment → Zen; add `OPENCODE_ZEN_API_KEY` and `OPENCODE_AGENT`; keep a Groq alternative commented.

### Phase 2 — Observability (Capture → Cloudinary → API)

#### 2.1 New service `backend/app/services/opencode_logger.py`
- `OpenCodeLogCapture` class per session:
  - Spawns an SSE task on `GET <sidecar>/event`; derives per-session events by filtering bus payloads. Normalized entry model:
    ```json
    { "seq": 1, "ts": "ISO", "level": "info", "event": "part.updated",
      "phase": "coding", "step": "compile/test/edit/shell/tool",
      "message": "...", "data": { "tool": "bash", "input": "...", "result": "..." } }
    ```
  - Event-to-entry mapping for: title generation, `message.created/updated`, text deltas, tool calls/results (`tool.*`), shell (`bash.highlight`), file edits (`edit`/`write`), provider errors.
  - **Redaction/size guards:** strip `Authorization`, `X-Api-Key`, `apiKey` fields; cap any single `data` payload at 4KB; never emit sentinel/`GROQ_ZEN` key values.
  - `stop_capture()` → flattens NDJSON blob + a `<session>.summary.json` (tools used, files touched, tests passed/failed, repair turns, first error line) → `get_storage().upload_bytes(...)`.
- Fallback poller: when SSE drops, poll `GET /session/{id}/message` every 3s.
- In-process pub/sub channel (`asyncio.Queue` broadcast) so the chat SSE handler can republish live entries as `agent_log` events.
- `get_transcript(session_id)` helper for failure diagnostics.

#### 2.2 New index model `backend/app/models/opencode_log.py`
- Table `opencode_logs` (thin index only — payload lives in Cloudinary):
  ```
  id (uuid PK) · session_id (str, index) · build_id (FK mvp_builds, nullable, index)
  solution_id (FK solutions, nullable, index) · status (capturing|complete|failed)
  storage_key · entry_count · first_ts · last_ts · created_at · updated_at
  ```
- Register in `backend/app/models/__init__.py` (requires all tables on `Base.metadata` for tests).
- Alembic migration (autogenerate `alembic revision --autogenerate -m "opencode logs index"`).

#### 2.3 Hooks
- `mvp_builder.py`:
  - Wrap `create_session`/`send_message`/`send_build_prompt`/`run_build` (`:2450-2530`) with capture start/stop.
  - On provider/sidecar failure: `get_transcript(session_id)`, persist capture, upload summary, set `error_message` with an actionable first line (e.g. "Zen 401 — re-check OPENCODE_ZEN_API_KEY").
- `opencode_chat.py` chat stream:
  - At `agent_start` (session created) → `capture.start`.
  - Between `build_progress` events → republish normalized entries as event `"agent_log"` (`json.dumps(entry)`).
  - On `complete`/`error` → `capture.stop()` + index row upsert.

#### 2.4 New API endpoints (`opencode_chat.py` router, auth + ownership-checked)
- `GET /api/v1/opencode/sessions/{session_id}/logs?limit=&offset=` → resolve index row → `storage.download_raw(key)` → return entries (paginated) + `summary`.
- `GET /api/v1/opencode/builds/{build_id}/logs` → join `MVPBuild.opencode_session_id` → same as above.
- `GET /api/v1/opencode/diagnose` → sidecar diagnosis report:
  ```json
  { "ok": bool, "healthy": bool, "version": "...", "model": "...", "agent": "...",
    "providers_connected": [ "opencode" ], "tooling": { "node": "...", "python": "...",
    "git": "...", "rg": "..." },
    "checks": [ { "name": "zen-auth", "status": "ok|warn|fail", "detail": "...", "fix": "..." } ] }
  ```
  Checks: server reachable; resolved model not empty; Zen provider connected; tooling binaries present; and a tiny real session round-trip against Zen (create session → `noReply` ping) with the raw error surfaced. `fix` string is copy-pasteable (e.g. `export OPENCODE_ZEN_API_KEY=...`).

### Phase 3 — Frontend

#### 3.1 `frontend/src/lib/api.ts`
- Extend `opencodeApi`: `logs(sessionIdOrBuildId, params)`, `diagnose()`, `listBuildLogs(buildId)`.
- `streamSSE` handler pipeline: add `agent_log` to typed event union; export `OpenCodeLogEntry` + `OpenCodeDiagnosis` types.

#### 3.2 Chat page `frontend/src/app/(dashboard)/chat/page.tsx`
- Add collapsible "Agent logs" panel under the build progress card.
- Live: on `agent_log` append entry to a local list (level badge, phase, ts, message).
- Historical: "Refresh logs" button → `opencodeApi.logs(sessionId)`; render with existing Tailwind/sutra styles.
- On error: show first-line `fix` hint from the log summary.

#### 3.3 MVP build view + Dashboard
- Build details: "Logs" tab → `getBuildLogs(buildId)`.
- `(dashboard)/dashboard/page.tsx` engine banner: show `sidecar_healthy` + `mode` (already present) and add "Diagnose" → modal rendering `diagnose()` checklist with red/amber/green statuses and copy-button on `fix` strings.

### Phase 4 — Ops, Docs, Verification

#### 4.1 Ops
- `Makefile` (root): `sidecar-build`, `sidecar-up`, `sidecar-logs` (`docker logs -f ai_solution_builder_opencode`), `sidecar-diagnose` (curl diagnose endpoint).
- README: "OpenCode sidecar" section — prerequisites (`OPENCODE_ZEN_API_KEY`), runbook (container not starting / agent 401 / provider not connected), log retrieval.
- ADR: `docs/adr/opencode-sidecar-observability.md` — decision record: Zen primary provider; invalid `{env:...:-...}` bug; Cloudinary log storage + DB index.

#### 4.2 Verification (acceptance)
1. `docker build -t opencode-sidecar:test backend/opencode` → exits 0.
2. `OPENCODE_ZEN_API_KEY=<key> docker compose up -d postgres redis opencode` → `GET http://localhost:4096/global/health` returns `{healthy:true, version}`; `docker compose logs opencode` shows diag banner + no FATAL.
3. `GET http://localhost:4096/doc` reachable; `GET http://localhost:4096/provider` shows `connected: ["opencode"]`.
4. Live session round-trip: create session → send `"Reply with exactly: OK"` → expect assistant part containing `OK` (proves Zen key + agent config).
5. `GET /api/v1/opencode/diagnose` → all checks `ok`, `ok: true`.
6. Run one MVP build end-to-end (`POST /api/v1/mvp/{solution_id}/build`) → `opencode_logs` index row exists, Cloudinary object uploaded, `GET /builds/{id}/logs` returns entries.
7. Full backend pipeline: `ruff check . && ruff format . && mypy src/ --strict && pytest tests/ -v`.

#### 4.3 New tests (`backend/tests/`)
- `test_opencode_logger.py`: entry normalization, secret redaction, 4KB cap, NDJSON round-trip, transcript fallback.
- `test_opencode_diagnose.py`: mocked builder.probe → `ok:true`; provider 401 → `ok:false` + `fix` present.
- `test_opencode_logs_api.py`: endpoint ownership checks (403 for foreign session), pagination.
- Extend `test_mvp_builder.py`/`test_opencode_chat.py` for capture start/stop wiring (mocked).

---

## 4. Open Items (validated live during implementation)

- Exact `auth.json` schema for Zen (`@opencode/cli` 1.18.31) + whether `PUT /auth/opencode` is safe to use as the fallback path.
- Exact `/event` SSE bus payload shape for each part/tool type (map events empirically against a live session).
- Cloudinary `raw` public_id constraints for long `session_id` keys (dashes only → safe; verify length limits).
- Whether `small_model` on Zen is required for title generation to avoid the default `gpt-5-nano` call.

---

## 5. Rollout & Rollback

- **Rollout:** 1) sidecar image + compose/fly/render config; 2) logger/index/migration + API; 3) frontend panels. Backwards compatible: capture is additive, and `/health` shape unchanged.
- **Rollback:** revert compose config model wiring; logger fails open (DB write exceptions suppressed; Cloudinary upload failure degrades to local `error_message` only).