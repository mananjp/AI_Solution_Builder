# Baseline — 2026-10-10

This is a recorded baseline, not a release sign-off. Commands were run from a
clean source checkout before production-hardening changes.

| Check | Result | Evidence / blocker |
| --- | --- | --- |
| Backend lint, format, types, tests | Blocked initially | The default Python 3.14 environment had none of `ruff`, `mypy`, or `pytest`. The project pins Python 3.12-compatible dependencies; a Python 3.12 virtual environment is required. |
| Focused changed-file Ruff check | Passed | `ruff check app/services/security/archive.py app/core/errors.py app/core/middleware.py tests/test_archive_security.py` |
| Focused changed-file Ruff format | Passed | `ruff format --check` on the same files |
| Focused archive tests | Blocked at collection | `tests/conftest.py` imports the full application; its LangChain runtime was not yet installed in the isolated QA environment. |
| `pip-audit` | Blocked | Not installed in the original environment. |
| Frontend `npm ci`, lint, typecheck, build | Blocked | Package installation hit registry DNS failures (`EAI_AGAIN`) and npm cannot write its default cache under `/home/codespace/.npm`. |
| `docker compose build` | Blocked | Docker Buildx cannot create `/home/codespace/.docker/buildx` because that directory is read-only. |
| Alembic heads | Blocked initially | Alembic was unavailable in the original interpreter. |

## Static facts

- `extractall` call sites under `backend/app`: 0.
- `safe_extract_zip` call sites under `backend/app`: 10 references (definition,
  exports, and six extraction integrations).
- Broad `except Exception:` sites under `backend/app`: 35. This is a confirmed
  production-hardening gap; several are intentional fallbacks but all need
  individual classification before a zero-silent-swallow claim is credible.
- Compose defines six services: `postgres`, `redis`, `backend`, `worker`,
  `opencode`, and `frontend`.
- CI currently builds deprecated root `app.Dockerfile` and `builder.Dockerfile`
  despite compose using separate backend, worker, sidecar, and frontend images.

## Audit claims reconciled so far

- **False:** the audit's Next.js 15.3.3 claim. `frontend/package.json` pins
  Next.js 16.3.4.
- **Confirmed:** archive extraction is centralized through `safe_extract_zip`;
  the initial implementation still required hardening for symlinks, actual
  written bytes, and executable file modes.
- **Partial:** the API error envelope existed, but it omitted `request_id`.
