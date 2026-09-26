# AI Solution Builder — Threat Scanning Implementation Plan

Status: APPROVED (design), implementation pending.
Ticket: `SEC-SCAN-001`
Component: Backend (`app/services/security/`, `app/api/upload.py`, `app/api/legacy_repo.py`, `app/api/export.py`, `app/services/mvp_builder.py`, `app/services/deployer.py`, `app/core/config.py`)

---

## Locked Decisions

- **Architecture**: A three-layer `Scanner` fan-out behind one orchestrator. Layer 0 local rules (offline, always on) → Layer 1 ClamAV (optional, unlimited) → Layer 2 VirusTotal (opt-in, ToS-restricted).
- **VirusTotal Public API is NOT a production layer.** We hold a free Community key. VT's own docs: *"The Public API is limited to 500 requests per day and a rate of 4 requests per minute. The Public API must not be used in commercial products or services... Noncompliance of these terms will result in immediate permanent ban."* This product is commercial (Razorpay/Stripe billing, metered credits, paid Render/Vercel deploys). VT ships **disabled**, gated behind an explicit `VIRUSTOTAL_ACK_TOS` acknowledgement that raises at boot.
- **What actually protects production** is Layer 0 + Layer 1. Both are unlimited and ToS-clean, and they cover the real attack surface: polyglot/extension-spoofed files, macro-laden Office docs, zip bombs, path traversal. VT is a bonus signal in local development.
- **Enforcement is two independent dials**, never one:
  - `SECURITY_SCAN_BLOCK_THRESHOLD` — what counts as a finding (`malicious` | `suspicious`).
  - `SECURITY_SCAN_FAIL_UNAVAILABLE_MODE` — what happens when a scanner is down / quota-exhausted (`allow` | `quarantine` | `block`).
  A scanner outage must never escalate a verdict; a clean verdict must never mask a scanner outage.
- **Latency**: Layer 0/1 run **synchronously inline** (milliseconds, no quota). VT runs **asynchronously on the worker** behind a quota-shaped token bucket. Files >32 MB are never uploaded to VT.
- **Caching is the feature, not an optimization.** The 4 req/min ceiling is the binding constraint on the VT path, so verdicts — clean ones especially — cache on `sha256` / `url_id` for 7 days. Repeat content costs zero requests.
- **Zero new pip dependencies.** ClamAV is spoken over raw TCP (`zINSTREAM`), which keeps the `pip-audit` surface unchanged and the image smaller.
- **The archive hardening ships first and is independent of everything else.** `guard_archive()` is sync, offline, and must never depend on VT or ClamAV availability.
- **Deferred (not this pass)**: scanning LLM-generated *text* (not AV-scannable); redirect-hop scanning; scanning npm dependencies of generated projects; VT Private/Premium tier.

---

## Phase 0 — Pre-flight (non-blocking)

Run `opencode --version`, compare to the latest release.

- **Patch** (`1.18.32` → `1.18.40`): do NOT update; defer.
- **Minor/Major** (`1.18.32` → `1.19.0`): show the maintenance notice, ask, upgrade only on explicit approval. A declined or failed upgrade is **not** a build failure — continue.

Baseline recorded at plan time: `1.18.32`.

---

## Phase 1 — Vocabulary, interface, config

### 1.1 `app/services/security/types.py` (new)

Core vocabulary shared by every layer. `mypy --strict`-clean.

```python
class ScanVerdict(str, Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"
    ERROR = "error"
    SKIPPED = "skipped"

class ScanTarget(str, Enum):
    FILE = "file"
    URL = "url"
    ARCHIVE = "archive"

@dataclass(frozen=True, slots=True)
class ScanFinding:
    source: str                 # "local_rules" | "clamav" | "virustotal"
    verdict: ScanVerdict
    reason: str                 # stable machine code, e.g. "exec_magic_mismatch"
    detail: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ScanResult:
    verdict: ScanVerdict
    findings: tuple[ScanFinding, ...] = ()
    sha256: str | None = None
    url: str | None = None
    scanned_bytes: int = 0
    duration_ms: float = 0.0
    from_cache: bool = False
```

Severity ranking helper `_worst(findings) -> ScanVerdict` implementing `MALICIOUS > SUSPICIOUS > UNKNOWN > CLEAN > SKIPPED`, with `ERROR` deliberately excluded from escalation (it is surfaced as a separate signal, not a verdict).

### 1.2 `app/services/security/base.py` (new)

```python
class Scanner(Protocol):
    name: str
    def available(self) -> bool: ...
    async def scan_bytes(self, data: bytes, *, filename: str) -> ScanResult: ...
    async def scan_url(self, url: str) -> ScanResult: ...
```

`Protocol` (not ABC) so adapters stay structurally typed and trivially fakeable in tests — matches how `test_render_deployer.py` already fakes a client.

### 1.3 `app/services/security/__init__.py` (new)

Re-export `ScanResult`, `ScanVerdict`, `ScanTarget`, `ScanFinding`, and the orchestrator's public entry points. Routes import only from here.

### 1.4 `app/core/config.py` — new settings block

Insert after the "Object Storage" block, before `TRUST_PROXY_HEADERS`:

```python
# ── Security / Threat Scanning ────────────────────
SECURITY_SCAN_ENABLED: bool = True
SECURITY_SCAN_BLOCK_THRESHOLD: str = "suspicious"      # malicious | suspicious
SECURITY_SCAN_FAIL_UNAVAILABLE_MODE: str = "allow"    # allow | quarantine | block
SECURITY_SCAN_SOURCES: str = ""                        # glob allowlist, e.g. "upload.*,legacy_repo.*"; "" = all
SECURITY_CACHE_TTL: int = 604800                       # 7 days
SECURITY_QUARANTINE_DIR: str = ".data/quarantine"

CLAMAV_ENABLED: bool = False
CLAMAV_HOST: str = "clamav"
CLAMAV_PORT: int = 3310
CLAMAV_TIMEOUT: float = 5.0

# ── VirusTotal (Layer 2 — OFF by default) ────────
# NOTE: the free Community API is limited to 4 req/min and 500 req/day and
# "must not be used in commercial products or services" (VT docs, Getting
# started). This layer is a local-dev signal only unless a commercial licence
# is in place. VIRUSTOTAL_ACK_TOS must be explicitly set to acknowledge the
# usage terms before the layer can be switched on at all.
VIRUSTOTAL_ENABLED: bool = False
VIRUSTOTAL_ACK_TOS: bool = False
VIRUSTOTAL_API_KEY: str = ""
VIRUSTOTAL_TIMEOUT: float = 15.0
VIRUSTOTAL_UPLOAD_TIMEOUT: float = 60.0
VIRUSTOTAL_MAX_UPLOAD_BYTES: int = 33554432             # VT POST /files hard cap: 32 MB
VIRUSTOTAL_MIN_DETECTIONS: int = 3
VIRUSTOTAL_CACHE_TTL: int = 604800
VIRUSTOTAL_RPM: int = 4
VIRUSTOTAL_DAILY: int = 500
VIRUSTOTAL_ASYNC: bool = True

SCAN_URL_INGEST: bool = True
SCAN_GENERATED_ARTIFACTS: bool = False                 # flip on after measuring FPs

ARCHIVE_MAX_ENTRIES: int = 10000
ARCHIVE_MAX_UNCOMPRESSED_BYTES: int = 524288000        # 500 MB
ARCHIVE_MAX_RATIO: int = 100
ARCHIVE_MAX_NESTED_DEPTH: int = 2
```

Three validator changes to the existing `Settings` class:

1. Add `VIRUSTOTAL_API_KEY` to the existing `clean_cloudinary_creds`-style quote-stripping validator (keys get pasted from the VT UI with quotes attached). Rename the validator to `clean_pasted_creds` and keep it applied to all four Cloudinary + VT keys.
2. New `@model_validator(mode="after") def enforce_scanner_config`:
   - **raises** `ValueError` if `VIRUSTOTAL_ENABLED and not VIRUSTOTAL_ACK_TOS`;
   - **raises** if `SECURITY_SCAN_BLOCK_THRESHOLD` not in `{malicious, suspicious}`;
   - **raises** if `SECURITY_SCAN_FAIL_UNAVAILABLE_MODE` not in `{allow, quarantine, block}`;
   - `logger.warning` if `VIRUSTOTAL_ENABLED and APP_ENV == "production"` — not fatal, because a licensed premium key in production is legitimate, but it should be visible in the boot log.
3. `case_sensitive = True` is already set, so all new env var names must match exactly.

---

## Phase 2 — Archive hardening (ships first, standalone value)

### 2.1 `app/services/security/archive.py` (new)

Two responsibilities. Both are **synchronous and offline** — they must work when every network scanner is down.

**`guard_archive(zip_bytes: bytes, *, source: str) -> None`**

Runs against `ZipFile.infolist()` only, so it inspects the central directory without decompressing anything. Cheap and safe. Raises `ScanBlockedError` on:

- total uncompressed size > `ARCHIVE_MAX_UNCOMPRESSED_BYTES` (zip bomb);
- any single entry's uncompressed size over the same cap;
- compression ratio > `ARCHIVE_MAX_RATIO` for any entry (nested/recursive bomb);
- entry count > `ARCHIVE_MAX_ENTRIES`;
- an entry with the encrypted flag set, or a ZIP64 marker with a suspect ratio;
- nesting depth > `ARCHIVE_MAX_NESTED_DEPTH` (zip → zip → zip → … is a packing/masquerade signal).

**`safe_extract_zip(zip_bytes: bytes, dest: Path) -> Path`**

The hardened successor to `_extract_zip_to_workspace` (`app/api/legacy_repo.py:229`). Hardening over the current implementation:

| Current behaviour | Replacement |
|---|---|
| `str(extracted_path).startswith(str(workspace_dir.resolve()))` — prefix comparison, fragile on case-insensitive filesystems and symlinked parents | `PurePosixPath` normalisation + explicit rejection of absolute paths, `..` segments, drive letters (`C:`), and backslash separators, then a `Path.relative_to()` containment assertion after resolution |
| No size, ratio, count, or nesting limits | Calls `guard_archive()` first |
| `extractall()` | `zf.open()` → `shutil.copyfileobj()` per vetted member, so each member is re-checked at write time |
| Unwraps a single root folder after extraction | Preserved (GitHub zipballs need it) |

### 2.2 Replace all five `extractall` call sites

Four of these have **no path-traversal guard today** and are the highest-value fix in this change set.

| Site | Current state | Action |
|---|---|---|
| `app/api/legacy_repo.py:238` | guarded (prefix check) | delegate to `safe_extract_zip` |
| `app/api/mvp.py:724` | **unguarded** | delegate |
| `app/api/mvp.py:1554` | **unguarded** | delegate |
| `app/api/mvp.py:1837` | **unguarded** | delegate |
| `app/services/deployer.py:152` | **unguarded** | delegate |

Delete `_extract_zip_to_workspace` from `legacy_repo.py` and update its two callers (`:285`, `:328`).

**Regression risk to watch**: `mvp.py:724` extracts build artifacts and `deployer.py:152` extracts the artifact before a GitHub push. `safe_extract_zip` must preserve the "unwrap single root directory" behaviour or deployment output changes shape. The test suite must be re-run in full, not just the security module.

---

## Phase 3 — Layer 0: `app/services/security/local_rules.py` (new)

Synchronous, offline, sub-millisecond. The layer that carries production.

| Check | Signal | Verdict |
|---|---|---|
| EICAR test string present | `"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"` | MALICIOUS |
| Executable magic (`MZ`, `\x7fELF`, Mach-O fat/64, `dex\n`, `\x00asm`, `\xca\xfe\xba\xbe`) | `exec_magic` | MALICIOUS |
| Executable magic but a document/data extension | `exec_magic_mismatch` (polyglot / extension spoof) | SUSPICIOUS |
| Extension↔magic disagreement (e.g. `%PDF-` named `.jpg`, ZIP magic named `.pdf`) | `magic_mismatch` | SUSPICIOUS |
| Denylist extension (`.exe .dll .scr .com .pif .bat .cmd .ps1 .psm1 .vbs .vbe .js .jse .wsf .ws .hta .msi .msp .jar .apk .lnk .reg .sh .bash .so .dylib .pyc .pyo .iso .img .vhd .cpl .chm .gadget`) | `denylisted_extension` | MALICIOUS |
| OLE2 compound-file magic (`\xd0\xcf\x11\xe0`) — legacy `.doc/.xls/.ppt`, macro carriers | `ole2_compound` | SUSPICIOUS |
| OOXML macro payload in a ZIP: `word/vbaProject.bin`, `xl/vbaProject.bin`, `ppt/vbaProject.bin` | `ooxml_macro` | MALICIOUS |
| `.xlsm` / `.docm` / `.dotm` / `.pptm` extension | `macro_enabled_office` | MALICIOUS |
| Nested archive depth > `ARCHIVE_MAX_NESTED_DEPTH` | `excessive_nesting` | SUSPICIOUS |
| Path traversal or absolute member name in a ZIP | `archive_traversal` | MALICIOUS |
| High-entropy blob with a benign text extension (possible packed payload) | `high_entropy_blob` | SUSPICIOUS |

Notes for implementation:

- Top-level denylist → MALICIOUS is correct here because `app/api/upload.py` already allowlists only `pdf docx csv xlsx xls txt md json yaml yml` (+ audio, + image), so no legitimate upload can carry these.
- The EICAR check is not a joke: it is the canary that proves the wiring is real. A scanner integration that silently no-ops will still be caught by the test suite because of it.
- Magic-number detection is a fixed tuple of `(offset, bytes, label)` triples — no new dependency needed (`python-magic` binds to libmagic and is not worth the build weight).

---

## Phase 4 — Layer 1: `app/services/security/clamav.py` (new)

`clamd` accepts the `zINSTREAM\0` command over plain TCP. Implement the framing directly — roughly 30 lines — so **no new pip dependency** is introduced and the `pip-audit` surface is unchanged.

```python
def _chunks(data: bytes) -> Iterator[bytes]:     # 4-byte big-endian length prefix per chunk
    view = memoryview(data)
    for off in range(0, len(view), CHUNK):
        block = view[off:off + CHUNK]
        yield len(block).to_bytes(4, "big") + block

# wire format: b"zINSTREAM\0" + chunks + b"\x00\x00\x00\x00"
# response:  b"<stream>: OK\0"  or  b"<stream>: <Signature> FOUND\0"
```

- `available()`: short-timeout TCP connect probe, result cached for `CLAMAV_TIMEOUT * 12` so we do not probe on every request.
- `scan_bytes()`: `asyncio.open_connection(host, port)` → send → read → parse. `FOUND` → MALICIOUS, `OK` → CLEAN, `ERROR` → `ScanVerdict.ERROR` (never escalates).
- Connection failure / read timeout → `ScanVerdict.ERROR`; the orchestrator applies `SECURITY_SCAN_FAIL_UNAVAILABLE_MODE`.
- 32 MB+ payloads exceed the default `StreamMaxLength`; truncate and mark the finding `truncated=true` rather than erroring.

---

## Phase 5 — Layer 2: `app/services/security/virustotal.py` (new, disabled)

Deliberately mirrors `app/services/razorpay_gateway.py` (the cleanest existing reference): module-level base const, a `RuntimeError` subclass, `httpx.AsyncClient(timeout=...)` as an async context manager, manual status branching, `cast` for `dict[str, Any]`.

```python
VIRUSTOTAL_API_BASE = "https://www.virustotal.com/api/v3"

class VirusTotalError(RuntimeError): ...

def virustotal_configured(*, api_key: str) -> bool: ...

def url_identifier(url: str) -> str:
    """VT URL identifier: unpadded urlsafe base64 (RFC 4648 §3.2, VT 'URL identifiers')."""
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").strip("=")
```

Functions: `lookup_file`, `lookup_url`, `upload_file`, `poll_analysis`, `submit_url`.

- `lookup_file` → `GET /api/v3/files/{sha256}`; 404 → `ScanVerdict.UNKNOWN` (never an error), 429 → raise with `Retry-After` surfaced.
- `upload_file` → `POST /api/v3/files`; **refuse above `VIRUSTOTAL_MAX_UPLOAD_BYTES`** with a clear error.
- `poll_analysis` → `GET /api/v3/analyses/{id}`; caller decides whether to wait (`queued` → `in_progress` → `completed`).
- Verdict from `last_analysis_stats.malicious >= VIRUSTOTAL_MIN_DETECTIONS` → MALICIOUS; `>= 1` → SUSPICIOUS; else CLEAN.
- **Field allowlist only.** Read a small explicit subset (`last_analysis_stats`, `last_analysis_date`, `sha256`, `size`, `type_description`, `meaningful_name`, `reputation`) into `ScanFinding.detail`. Never persist or forward a full VT report — the Premium terms forbid redistribution.
- `app/services/security/ratelimit.py`: Redis-backed token bucket sized to `VIRUSTOTAL_RPM` / `VIRUSTOTAL_DAILY` using the existing `redis.asyncio` client, so the limit is shared across the API process and the worker. Returns a bool rather than blocking — the async path simply skips and retries next cycle.
- `app/services/security/cache.py`: verdict cache over the existing `redis_set_json` / `redis_get_json` (`app/core/redis.py:99`). Keys `scan:file:{sha256}` and `scan:url:{url_id}`. **Negative and clean results are cached too** — that is what keeps a busy dev day inside 500 req/day.

---

## Phase 6 — `app/services/security/orchestrator.py` (new)

The only module routes import.

```python
async def scan_file(data: bytes, *, filename: str, source: str) -> ScanResult
async def scan_url(url: str, *, source: str) -> ScanResult
def guard_archive(zip_bytes: bytes, *, source: str) -> None            # sync, offline
def enforce(result: ScanResult, *, source: str) -> None
def enforce_url(url: str, *, source: str) -> None
```

Behaviour:

1. `SECURITY_SCAN_ENABLED=false` or `source` not matching `SECURITY_SCAN_SOURCES` glob → return `ScanVerdict.SKIPPED` immediately (no work, no network).
2. Compute `sha256`. Cache hit → return the cached `ScanResult` with `from_cache=True`.
3. Run every `available()` layer concurrently via `asyncio.gather(..., return_exceptions=True)`.
4. Aggregate with `_worst()`. `ERROR` findings are attached but excluded from the verdict.
5. Cache the result (including CLEAN) for `SECURITY_CACHE_TTL`.
6. `enforce()` decides:
   - verdict at/above `SECURITY_SCAN_BLOCK_THRESHOLD` → raise `ScanBlockedError`;
   - all layers unavailable/errored → apply `SECURITY_SCAN_FAIL_UNAVAILABLE_MODE` (`allow` / `quarantine` / `block`);
   - otherwise → no-op.
7. `guard_archive()` is fully separate from the network path and always runs before any extraction.

Errors, mapped into the **existing** `app/core/errors.py` envelope so no new response shape is introduced:

| Condition | HTTP | `error.code` |
|---|---|---|
| Detection above threshold | 422 | `SECURITY_SCAN_BLOCKED` |
| Scanner unavailable + `fail_mode=quarantine` | 403 | `SECURITY_QUARANTINED` |
| Scanner unavailable + `fail_mode=block` | 503 | `SCANNER_UNAVAILABLE` |
| Zip bomb / traversal / nesting | 422 | `SECURITY_ARCHIVE_REJECTED` |

Every outcome (including `SKIPPED`) persists a `ScanRecord` so the admin surface and audit trail are complete.

---

## Phase 7 — Persistence

### 7.1 `app/models/scan.py` (new)

`ScanRecord(Base)`, `__tablename__ = "scan_records"`, mirroring the style of `app/models/audit.py`:

`id UUID pk`, `sha256 String(64) index nullable`, `url String(2048) nullable`, `target String(10)`, `source String(40) index`, `verdict String(16) index`, `findings JSONB`, `scanned_bytes Integer`, `from_cache Boolean`, `user_id UUID nullable index`, `org_id UUID nullable`, `request_id String(64)`, `duration_ms Integer`, `created_at DateTime(timezone=True) index`.

Register in `app/models/__init__.py` (which already re-exports all 16 models) so `Base.metadata.create_all` in `main.py`'s lifespan picks it up in dev.

### 7.2 `alembic/versions/f3a4b5c6d7e8_create_scan_records.py` (new)

`down_revision` = the current head (`e7f8a9b0c1d2_add_file_list_to_mvp_builds.py` lineage — confirm with `alembic heads` before writing, since several revisions share the `x1a2b3c4d5e6`-style placeholder IDs). `downgrade()` drops the table. Must apply cleanly on both PostgreSQL (CI, `pgvector/pgvector:pg16` on 5433) and SQLite (local dev).

---

## Phase 8 — Admin surface + observability

### 8.1 `app/api/security.py` (new)

`APIRouter(prefix="/security", tags=["Security"])`, all endpoints admin-gated via the existing `_require_admin` from `app/api/admin.py` (factor it into `app/core/security.py` and import from both so there is one definition).

- `GET /api/v1/security/scans` — recent records, filter by `verdict` / `source`, paginated.
- `GET /api/v1/security/stats` — counts by verdict and source, p50/p95 duration, cache hit rate, block rate.
- `GET /api/v1/security/config` — masked config; reports which layers are `live`, and whether `VIRUSTOTAL_ACK_TOS` is set. Never echo the key (reuse the `mask_secret` helper from `app/services/legacy_repo/credentials.py:28`).
- `POST /api/v1/security/scan/file` — on-demand scan of an admin-uploaded file.

Register in `main.py` alongside the other routers.

### 8.2 `app/core/metrics.py`

Add `scans_total{source,verdict}`, `scan_duration_seconds{source}` (histogram), `scan_blocked_total{source}`, `scan_cache_hits_total`, and `scanner_up{scanner}`. Expose `set_scanner_health(name, up)` and have `/ready` (`app/api/system.py:40`) report scanner status in its `checks` dict alongside `database` / `redis` — if a required layer is down, `/ready` should go 503 only when `fail_mode=block`.

---

## Phase 9 — Integration points (10 hooks)

Every guard runs **before** the dangerous operation, never after.

### Outside → in

| # | Site | Guard |
|---|---|---|
| 1 | `app/api/upload.py:33` `upload_url` | `enforce_url(payload.url, source="upload.url")` before `parse_url` |
| 2 | `app/api/upload.py:85` `upload_document` | `enforce_file(contents, filename, source="upload.document")` before `parse_document` — PyMuPDF / `pandas.read_excel` on hostile input is the concrete risk here |
| 3 | `app/api/upload.py:142` `upload_audio` | `enforce_file(...)` **before** the `AsyncGroq` Whisper call — stops a malware-laden file being shipped to a third party, and stops the data egress |
| 4 | `app/api/upload.py:195` `upload_image` | `enforce_file(...)` before the vision-context branch |
| 5 | `app/api/upload.py:231` `import_existing_system` | `enforce_url(payload.github_repo, source="upload.system")` before the README fetch |
| 6 | `app/api/legacy_repo.py:328` `analyze_uploaded_repository_zip` | `guard_archive(contents)` (sync) **then** `enforce_file(...)` **before** `_extract_zip_to_workspace` |
| 7 | `app/api/legacy_repo.py:281` GitHub zipball path | `enforce_file(zip_content, filename=f"{owner}-{repo}.zip", source="legacy_repo.github")` before extraction |

### Inside → out

| # | Site | Guard |
|---|---|---|
| 8 | `app/api/export.py:222` deployable ZIP | `enforce_file(zip_buffer.getvalue(), filename, source="export.zip")` before the `StreamingResponse` — catches prompt-injected payloads smuggled into generated code. Gated on `SCAN_GENERATED_ARTIFACTS` |
| 9 | `app/services/mvp_builder.py:3156` `package_build` | same, same gate |
| 10 | `app/services/deployer.py:152` | replace `extractall` with `safe_extract_zip` (Phase 2.2) |

Additionally, for genuine prompt-injection egress coverage: extract URLs from generated content (spec, HTML, generated source) and run `enforce_url` on each before serving or deploying. Implement as `enforce_urls_in_text(text, *, source)` in the orchestrator, called from the artifact-serve and deploy paths when `SCAN_GENERATED_ARTIFACTS=true`.

---

## Phase 10 — Tests: `backend/tests/test_security_scan.py` (new)

House style: `unittest.mock.AsyncMock` / `MagicMock` / hand-rolled fakes via `monkeypatch`. **No `respx`, no `pytest-httpx`, no VCR** — consistent with `test_render_deployer.py` and `test_storage.py`.

`conftest.py` sets `SECURITY_SCAN_ENABLED=true` with ClamAV and VT **off**, so the suite exercises Layer 0 only: fully deterministic, **zero network**, no quota consumption.

Coverage:

- **local rules** — EICAR; `MZ` renamed `.pdf`; `%PDF-` renamed `.jpg`; VBA-macro `.docx` → MALICIOUS; each denylist extension; OLE2 legacy Office; nested depth exceeded; high-entropy blob.
- **archive** — zip-slip via `../`; absolute path `/etc/passwd`; backslash separator; drive letter; ratio bomb; entry-count cap; oversized uncompressed; encrypted entry; nesting depth.
- **safe_extract** — valid archive extracts and unwraps a single root dir; traversal raises; asserts via `grep`-style introspection that all five former `extractall` sites now route through it.
- **virustotal client** — `url_identifier` strips `=` padding and is urlsafe; 404 → `UNKNOWN` (not an error); 429 → `VirusTotalError`; >32 MB upload refused; `MIN_DETECTIONS` threshold boundary; `poll_analysis` state machine. All HTTP via `AsyncMock`.
- **ratelimit** — bucket admits `VIRUSTOTAL_RPM` then denies; daily cap trips; Redis down → fail-open.
- **orchestrator** — cache hit performs **no** HTTP; worst-of aggregation ordering; `ERROR` never escalates; `SKIPPED` when disabled or source excluded; the full 3×3 matrix of `BLOCK_THRESHOLD` × `FAIL_UNAVAILABLE_MODE`.
- **endpoints** — EICAR ZIP → `/api/v1/legacy-repo/analyze-upload` returns 422 with `error.code == "SECURITY_SCAN_BLOCKED"`; `MZ`-in-`.pdf` → `/api/v1/upload/document` returns 422; a clean upload still succeeds 200.
- **regression** — the existing `test_mvp_api.py`, `test_legacy_repo.py`, and `test_chat_artifacts_export.py` suites must stay green after the `extractall` swap.

Repo gate is `--cov-fail-under=70` in `backend/pyproject.toml`; the new module must not pull the total below it.

---

## Phase 11 — Config surfaces, CI, docs

- **`.env.example`** — new `SECURITY_SCAN_*`, `CLAMAV_*`, `VIRUSTOTAL_*`, `ARCHIVE_MAX_*` block with the VT ToS warning inline as a comment, mirroring the existing `JWT_SECRET_KEY` warning style.
- **`docker-compose.yml`** — optional `clamav/clamav:1.4` service with a `clamdscan --ping` healthcheck; `backend` gains `depends_on` with `condition: service_healthy`; a `profiles: [security]` tag so the default stack is unchanged for contributors who do not want it.
- **`.github/workflows/ci.yml`** — the existing `backend` job already runs lint → mypy → migrate → pytest → pip-audit, which covers the new module with no structural change. Add a dedicated `pytest tests/test_security_scan.py -v` step ahead of the full suite so a security regression fails fast and legibly. No new pip dependencies, so the `pip-audit` step is unchanged.
- **`docs/security-scanning.md`** — architecture, the layer table, every env var, the enforcement matrix, the VT ToS constraint and why it defaults off, and the documented limitations below.
- **`docs/adr/0001-threat-scanning.md`** — ADR per the backend protocol: context, decision, consequences, rejected alternatives (VT-only; blocking-everything fail-closed; `python-magic`; a heavyweight `clamav` pip binding).

---

## Documented limitations (state these plainly in the ADR)

1. VT's URL report is **reputation, not a fetch-time verdict**. Redirect hops are not scanned — only the submitted URL. A benign URL that redirects to a payload passes.
2. Files above 32 MB are never uploaded to VT, so they get no Layer 2 signal at all. Layers 0/1 still apply.
3. LLM-generated **text** is not AV-scannable. Archive-level scanning of the packaged result is the ceiling for the egress path.
4. A clean ZIP can still contain a script that only misbehaves after `npm install` / `npm run build`. Scanning the archive does not equal scanning what it produces.
5. With a free key the VT layer sees 4 req/min and 500 req/day. Caching + the token bucket keep us legal, but a busy day will still starve that layer. This is exactly why it is not a production dependency.
6. ClamAV detection lags new malware by hours-to-days. Layer 0's structural checks are the only same-request defence.

---

## Acceptance criteria

- [ ] `guard_archive` rejects zip-slip, absolute paths, ratio bombs, entry-count bombs, and excessive nesting in tests.
- [ ] All five `extractall` call sites delegate to `safe_extract_zip`; the four previously-unguarded ones are closed.
- [ ] EICAR and macro-bearing Office documents are rejected at every one of the seven outside→in hooks.
- [ ] A detection returns 422 with `error.code == "SECURITY_SCAN_BLOCKED"` in the existing envelope shape.
- [ ] A scanner outage produces no verdict escalation; `allow` / `quarantine` / `block` each behave as specified.
- [ ] A cache hit issues zero outbound HTTP requests (asserted by mock call-count).
- [ ] The app refuses to boot with `VIRUSTOTAL_ENABLED=true` and `VIRUSTOTAL_ACK_TOS=false`.
- [ ] With ClamAV and VT off, the whole test suite runs with zero network access and stays green.
- [ ] Coverage stays at or above the repo's 70% gate.
- [ ] **Zero new pip dependencies.**
- [ ] `ruff check`, `ruff format --check`, `mypy app/`, `pytest tests/`, `pip-audit -r requirements.txt`, and `docker build` all pass.

---

## Build pipeline (run in this order; stop on any failure)

1. `opencode --version` — non-blocking pre-flight.
2. `ruff check . && ruff format --check .`
3. `mypy app/`
4. `pytest tests/ -v --cov=app --cov-report=term-missing`
5. `pip-audit -r requirements.txt`
6. `docker build -f backend.Dockerfile -t ai-solution-builder-backend:test .`
7. `trivy fs .` (or `aquasec/trivy fs`) — if Trivy or the Docker daemon is unavailable in this environment, **report that explicitly**; do not let the step pass silently.

On failure: stop, report the exact error, fix the root cause, re-run from step 2. Never skip a step. A failed `opencode upgrade` is explicitly not a build failure.
