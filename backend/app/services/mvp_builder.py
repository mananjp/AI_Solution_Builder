"""
AI Solution Builder — OpenCode MVP Builder Service

Drives the OpenCode sidecar (HTTP proxy) to convert validated solution
artifacts (HLD, LLD, ER diagram, API spec, DDL, wireframes) into a working
functional MVP prototype.

Architecture:
    FastAPI backend  --httpx-->  opencode serve (sidecar container)
                                        |
                     writes generated source files to a shared volume
                                        |
    FastAPI reads the filesystem directly to list / package the project

The sidecar server runs with its current working directory on a shared
volume. Each build is scoped to a `<solution_id>/build_<n>` subdirectory
chosen by this service and passed inside the generated prompt, so multiple
builds never collide.
"""

import asyncio
import base64
import io
import json
import logging
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_IGNORED = {".git", "node_modules", "__pycache__", ".next", ".venv", "venv", "dist", "build"}

# Retry configuration for OpenCode API calls
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 5  # seconds
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


class MVPBuilderError(RuntimeError):
    """Raised when a build cannot be started or completed."""


def workspace_root() -> Path:
    """Local (backend) path mirroring the sidecar's /workspace volume."""
    root = Path(settings.MVP_BUILD_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_workspace_dir(solution_id: UUID, build_number: int) -> Path:
    """Return the host path for a solution/build workspace, creating it."""
    project_dir = workspace_root() / solution_id.hex[:12]
    build_dir = project_dir / f"build_{build_number}"
    build_dir.mkdir(parents=True, exist_ok=True)
    return build_dir


def _container_target(solution_id: UUID, build_number: int) -> str:
    """Relative target directory inside the sidecar's /workspace."""
    return f"{solution_id.hex[:12]}/build_{build_number}"


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.OPENCODE_SERVER_PASSWORD:
        creds = base64.b64encode(f"opencode:{settings.OPENCODE_SERVER_PASSWORD}".encode()).decode(
            "ascii"
        )
        headers["Authorization"] = f"Basic {creds}"
    return headers


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.OPENCODE_SERVER_URL,
        headers=_auth_headers(),
        timeout=settings.MVP_BUILD_TIMEOUT,
    )


async def health() -> dict[str, Any]:
    """Check the OpenCode sidecar is reachable and healthy.

    Returns a dict with 'healthy' bool plus diagnostic details.
    """
    result: dict[str, Any] = {"healthy": False, "details": {}}
    try:
        async with _client() as client:
            resp = await client.get("/global/health", timeout=10.0)
            result["details"]["http_status"] = resp.status_code
            if resp.status_code != 200:
                result["details"]["error"] = f"HTTP {resp.status_code}"
                logger.warning("OpenCode sidecar unhealthy: HTTP %s", resp.status_code)
                return result
            body = resp.json()
            result["healthy"] = bool(body.get("healthy", False))
            result["details"] = {**result["details"], **body}
            logger.info(
                "OpenCode sidecar health: healthy=%s version=%s",
                result["healthy"],
                body.get("version", "unknown"),
            )
            return result
    except httpx.ConnectError as exc:
        result["details"]["error"] = f"Connection refused: {exc}"
        logger.warning("OpenCode sidecar unreachable (connection refused): %s", exc)
        return result
    except httpx.HTTPError as exc:
        result["details"]["error"] = str(exc)
        logger.warning("OpenCode sidecar unreachable: %s", exc)
        return result


async def _retry_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json_data: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff retry for transient failures."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.request(
                method,
                url,
                json=json_data,
                timeout=timeout or settings.MVP_BUILD_TIMEOUT,
            )
            if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES - 1:
                wait = RETRYBACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "OpenCode %s %s returned %s (attempt %d/%d), retrying in %ds",
                    method,
                    url,
                    resp.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = RETRYBACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "OpenCode %s %s failed (attempt %d/%d): %s — retrying in %ds",
                    method,
                    url,
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            raise
    # Should not reach here, but satisfy type checker
    raise last_exc or MVPBuilderError("Request failed after retries")


RETRYBACKOFF_BASE = RETRY_BACKOFF_BASE


async def create_session(title: str) -> str:
    """Create a new OpenCode session and return its id."""
    async with _client() as client:
        resp = await _retry_request(client, "POST", "/session", json_data={"title": title})
        if resp.status_code not in (200, 201):
            raise MVPBuilderError(
                f"Failed to create OpenCode session ({resp.status_code}): {resp.text[:500]}"
            )
        body: dict[str, Any] = resp.json()
        session_id = body.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise MVPBuilderError(
                f"OpenCode session response missing 'id'. Response: {json.dumps(body)[:300]}"
            )
        logger.info("OpenCode session created: %s", session_id)
        return session_id


async def send_build_prompt(session_id: str, prompt: str) -> dict[str, Any]:
    """Send the MVP build prompt and wait for the full assistant response."""
    payload: dict[str, Any] = {
        "agent": settings.OPENCODE_AGENT,
        "parts": [{"type": "text", "text": prompt}],
        "model": None,
    }
    async with _client() as client:
        resp = await _retry_request(
            client,
            "POST",
            f"/session/{session_id}/message",
            json_data=payload,
            timeout=settings.MVP_BUILD_TIMEOUT,
        )
        if resp.status_code not in (200, 201):
            body_text = resp.text[:800]
            raise MVPBuilderError(
                f"OpenCode build prompt failed ({resp.status_code}): {body_text}"
            )
        result: dict[str, Any] = resp.json()
        # Log the response info for debugging
        info = result.get("info", {})
        if isinstance(info, dict) and info.get("error"):
            logger.error("OpenCode agent reported error: %s", info["error"])
        return result


async def abort_session(session_id: str) -> None:
    """Abort a running session (best-effort)."""
    try:
        async with _client() as client:
            await client.post(f"/session/{session_id}/abort", timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("Failed to abort OpenCode session %s: %s", session_id, exc)


# ── Template scaffold ──────────────────────────────────────────────────


def template_root() -> Path:
    """Host path of the bundled MVP scaffold template."""
    backend_root = Path(__file__).resolve().parents[2]
    root = backend_root / settings.MVP_TEMPLATE_DIR
    if not root.is_dir():
        raise MVPBuilderError(f"MVP template directory not found: {root}")
    return root


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "app"


def _substitute(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        token = f"__{key}__"
        text = text.replace(token, value)
    return text


def _ignore_artifacts(directory: str, names: list[str]) -> set[str]:
    return {
        n
        for n in names
        if n in {".git", "node_modules", "__pycache__", ".next", "dist", "build", ".venv", "venv"}
    }


def scaffold_build(
    build_dir: Path | str,
    *,
    app_title: str,
    inject_modules: list[str],
) -> None:
    """Seed a build directory by copying the scaffold template.

    Copies the bundled template into `build_dir`, substitutes deterministic
    placeholders (app name/title/slug, JWT secret) so the agent only has to
    add module-specific code, keeping every prompt request small enough to
    fit the model's tokens-per-minute ceiling.
    """
    root = Path(build_dir)
    shutil.copytree(template_root(), root, dirs_exist_ok=True, ignore=_ignore_artifacts)

    app_name = _slugify(app_title)
    mapping = {
        "APP_NAME": app_name,
        "APP_TITLE": app_title,
        "APP_SLUG": app_name,
        "JWT_SECRET": "change-me-generated-jwt-secret",
    }

    # Apply substitutions to all text files carrying placeholders.
    _substitute_tree(root, mapping)
    logger.info("Scaffolded build %s from template (modules=%d)", root, len(inject_modules))


def _apply(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _substitute_tree(root: Path, mapping: dict[str, str]) -> None:
    text_extensions = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".mjs",
        ".json",
        ".yml",
        ".yaml",
        ".md",
        ".txt",
        ".ini",
        ".env.example",
        ".gitignore",
        ".example",
    }
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in text_extensions:
            _apply(path, _substitute(path.read_text(encoding="utf-8", errors="ignore"), mapping))


def _compact(text: str | None, limit: int = 2000) -> str:
    """Trim long artifact content to a compact one-liner."""
    if not text:
        return ""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _entity_summary(er_content: dict[str, Any]) -> str:
    entities = er_content.get("entities", []) if isinstance(er_content, dict) else []
    lines = []
    for ent in entities:
        if isinstance(ent, dict):
            name = ent.get("name", "")
            fields = ent.get("fields", [])
            if isinstance(fields, list):
                field_names = [f.get("name") if isinstance(f, dict) else f for f in fields]
            else:
                field_names = []
            lines.append(f"- {name}: {', '.join(map(str, field_names))}")
    return "\n".join(lines)


def _endpoint_summary(api_spec_content: dict[str, Any]) -> str:
    endpoints = api_spec_content.get("endpoints", []) if isinstance(api_spec_content, dict) else []
    return "\n".join(
        f"- {e.get('method', 'GET').upper()} {e.get('path', '')}"
        for e in endpoints
        if isinstance(e, dict)
    )


def build_mvp_prompt(
    ai_state: dict[str, Any], target_dir: str, app_title: str | None = None
) -> str:
    """Compose a compact MVP build prompt for the OpenCode agent.

    A full working scaffold (FastAPI + Next.js + infra) is copied into the
    target directory by the backend beforehand, so this prompt stays small
    enough to fit the model's tokens-per-minute ceiling. The agent only fills
    the artifact-specific slots: models, schemas, routers, and module pages.
    """
    title = (
        app_title
        or (ai_state.get("solution_title") or ai_state.get("business_description"))
        or "MVP"
    )
    industry = ai_state.get("industry", "general")
    product_type = ai_state.get("product_type", "full_stack_app")
    modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])
    brief = _compact(ai_state.get("business_description", ""), 900)

    hld = (
        ai_state.get("hld", {}).get("content", {}) if isinstance(ai_state.get("hld"), dict) else {}
    )
    lld = (
        ai_state.get("lld", {}).get("content", {}) if isinstance(ai_state.get("lld"), dict) else {}
    )
    er = (
        ai_state.get("er_diagram", {}).get("content", {})
        if isinstance(ai_state.get("er_diagram"), dict)
        else {}
    )
    api_spec = (
        ai_state.get("api_spec", {}).get("content", {})
        if isinstance(ai_state.get("api_spec"), dict)
        else {}
    )

    ddl = ""
    generated = ai_state.get("generated_schema")
    if isinstance(generated, dict):
        content = generated.get("content", {})
        if isinstance(content, dict):
            ddl = str(content.get("ddl", "")) or str(content.get("schema_ddl", ""))

    schema = ai_state.get("database_schema", {}).get("content", {})
    if not ddl and isinstance(schema, dict):
        ddl = str(schema.get("ddl", ""))
    if not ddl:
        ddl = json.dumps(schema, indent=2, default=str)

    wireframes = [
        wf.get("content", {})
        for wf in ai_state.get("wireframes", [])
        if isinstance(wf, dict) and isinstance(wf.get("content"), dict)
    ]
    wireframe_screens = []
    for wf in wireframes:
        for screen in wf.get("screens", []):
            if isinstance(screen, dict) and screen.get("name"):
                wireframe_screens.append(screen["name"])

    hld_overview = _compact(hld.get("system_overview") or hld.get("architecture"))
    lld_modules = lld.get("modules", [])

    build_context = [
        "# MVP Slot-Fill Request",
        "",
        f"**App:** {title} | **Industry:** {industry}",
        f"**Product type:** {product_type}",
        f"**Description:** {brief}",
        f"**Modules:** {', '.join(map(str, modules)) or 'general'}",
        f"**Target dir:** `{target_dir}`",
        "",
        "Do NOT rewrite the scaffold. Preserve the existing scaffold and only fill the required app-specific slots.",
        "Use the artifacts below as the source of truth; keep the build focused and complete.",
        "",
        "## Required edits",
        "- Insert model definitions above `__MODEL_INSERTION_POINT__` in models.py.",
        "- Insert CRUD routes above `__ROUTER_INSERTION_POINT__` in routers.py.",
        "- Keep the existing FastAPI + Next.js scaffold intact, but replace placeholder screens, forms, and copy with real product-specific code.",
        "- Build working module pages, navigation, and backend wiring from the supplied artifacts; do not leave generic templates in place.",
        "",
        "## Architecture context",
        f"HLD: {hld_overview or '_none provided_'}",
        f"LLD modules: {', '.join(str(m.get('name')) for m in lld_modules if isinstance(m, dict)) or 'none'}",
        "",
        "## ER entities",
        _entity_summary(er) or "_none provided_",
        "",
        "## API spec",
        _endpoint_summary(api_spec) or "_none provided_",
        "",
        "## Wireframes",
        "\n".join(f"- {s}" for s in wireframe_screens) or "_none provided_",
        "",
        "## Database DDL",
        "```sql",
        ddl.strip() or "_none provided_",
        "```",
        "",
        "## Rules",
        "- No secrets or placeholders; `.env.example` is the only place for example values.",
        "- No empty cards, lorem ipsum, or TODO comments.",
        "- Prefer a small complete product over a broad unfinished skeleton.",
        "- If a page is only a template, replace it with the actual workflow the artifacts describe.",
        "- Do not run installs, builds, or start servers; just edit files.",
        "- Report the finished screens, routes, and backend endpoints when done.",
    ]

    prompt = "\n".join(build_context)
    if len(prompt) > 3000:
        prompt = prompt[:2950].rstrip() + "\n..."
    return prompt


# ── Build execution ────────────────────────────────────────────────────


async def run_build(
    solution_id: UUID,
    ai_state: dict[str, Any],
    build_number: int,
    title: str | None = None,
) -> dict[str, Any]:
    """Run an OpenCode MVP build synchronously. Returns build result metadata."""
    health_result = await health()
    if not health_result["healthy"]:
        details = health_result.get("details", {})
        error_msg = details.get("error", "unknown")
        raise MVPBuilderError(
            f"OpenCode sidecar is not healthy ({error_msg}). "
            f"Ensure the opencode service is running and the model is available. "
            f"Details: {json.dumps(details)[:500]}"
        )

    target_dir = _container_target(solution_id, build_number)
    local_dir = build_workspace_dir(solution_id, build_number)

    app_title = title or (
        ai_state.get("solution_title") or ai_state.get("business_description") or "MVP"
    )
    modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])
    scaffold_build(
        local_dir,
        app_title=app_title,
        inject_modules=[str(m) for m in modules],
    )

    prompt = build_mvp_prompt(ai_state, target_dir, app_title=title)
    logger.info(
        "MVP build prompt: %d chars, target=%s, modules=%s",
        len(prompt),
        target_dir,
        modules,
    )

    session_id = await create_session(f"MVP Build - {title or solution_id}")
    logger.info("Starting MVP build for solution=%s (session=%s)", solution_id, session_id)

    try:
        response = await send_build_prompt(session_id, prompt)
        info = response.get("info", {})
        error_msg = info.get("error") if isinstance(info, dict) else None
        if error_msg:
            logger.error(
                "MVP build session reported error for solution=%s: %s",
                solution_id,
                error_msg,
            )
            raise MVPBuilderError(f"OpenCode agent error: {error_msg}")
        logger.info(
            "MVP build finished for solution=%s (session=%s)",
            solution_id,
            session_id,
        )
    except MVPBuilderError:
        await abort_session(session_id)
        raise
    except Exception as exc:
        logger.exception("MVP build unexpected error for solution=%s", solution_id)
        await abort_session(session_id)
        raise MVPBuilderError(f"Build failed unexpectedly: {exc}") from exc

    files = list_build_files(local_dir)
    if len(files) == 0:
        logger.warning(
            "MVP build produced no files for solution=%s (session=%s). "
            "The agent may have failed to write to the correct directory.",
            solution_id,
            session_id,
        )
        raise MVPBuilderError(
            "Build completed but produced no files. "
            "The agent may have written to an incorrect path. "
            f"Expected target: {target_dir}"
        )

    return {
        "session_id": session_id,
        "local_dir": str(local_dir),
        "file_count": len(files),
        "files": relative_paths(local_dir),
    }


# ── File tree helpers ──────────────────────────────────────────────────


def list_build_files(build_dir: Path | str) -> list[Path]:
    """Recursively list generated project files (excluding noise)."""
    root = Path(build_dir)
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in _IGNORED for part in path.parts):
            files.append(path)
    return files


def relative_paths(build_dir: Path | str) -> list[str]:
    """Return POSIX-style paths relative to the build directory."""
    root = Path(build_dir)
    return [str(p.relative_to(root)).replace("\\", "/") for p in list_build_files(root)]


def package_build(build_dir: Path | str) -> io.BytesIO:
    """Zip the generated project into an in-memory archive."""
    root = Path(build_dir)
    if not root.exists():
        raise MVPBuilderError("Build directory does not exist")
    files = list_build_files(root)
    if not files:
        raise MVPBuilderError("No generated files found in the build directory")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=str(path.relative_to(root)).replace("\\", "/"))
    buffer.seek(0)
    return buffer


# ── User config overlay ────────────────────────────────────────────────


def apply_config_overlay(
    build_dir: Path | str, app_name: str | None, env: dict[str, Any]
) -> dict[str, Any]:
    """Write a user-supplied config overlay (env values + app name) into the build."""
    root = Path(build_dir)
    if not root.exists():
        raise MVPBuilderError("Build directory does not exist")

    overlay: dict[str, Any] = {"app_name": app_name} if app_name else {}
    overlay.update(env or {})

    config_dir = root / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "app_config.json").write_text(
        json.dumps(overlay, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if env:
        lines = ["# User configuration overrides\n"]
        for key, value in env.items():
            lines.append(f"{key}={value}\n")
        (root / ".env.local").write_text("".join(lines), encoding="utf-8")

    if app_name:
        readme = root / "README.md"
        if readme.exists():
            text = readme.read_text(encoding="utf-8")
            readme.write_text(re.sub(r"^# .*", f"# {app_name}", text, count=1), encoding="utf-8")

    logger.info("Applied config overlay to %s (keys=%d)", root, len(overlay))
    return overlay


def cleanup_build(build_dir: Path | str) -> None:
    """Delete a build workspace (and empty parents) best-effort."""
    root = Path(build_dir)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
        for parent in (root.parent, root.parent.parent):
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
