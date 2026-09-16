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


def chat_container_target(solution_id: UUID) -> str:
    """Relative target directory inside the sidecar's /workspace for chat builds."""
    return f"{solution_id.hex[:12]}/chat"


def chat_workspace_dir(solution_id: UUID) -> Path:
    """Return the host path for a solution's OpenCode chat workspace."""
    project_dir = workspace_root() / solution_id.hex[:12]
    chat_dir = project_dir / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir


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


async def health() -> bool:
    """Check the OpenCode sidecar is reachable and healthy."""
    try:
        async with _client() as client:
            resp = await client.get("/global/health", timeout=10.0)
            if resp.status_code != 200:
                logger.warning("OpenCode sidecar unhealthy: HTTP %s", resp.status_code)
                return False
            body = resp.json()
            healthy = bool(body.get("healthy", False))
            logger.info("OpenCode sidecar healthy (version=%s)", body.get("version"))
            return healthy
    except httpx.HTTPError as exc:
        logger.warning("OpenCode sidecar unreachable: %s", exc)
        return False


async def create_session(title: str) -> str:
    """Create a new OpenCode session and return its id."""
    async with _client() as client:
        resp = await client.post("/session", json={"title": title})
        if resp.status_code not in (200, 201):
            raise MVPBuilderError(
                f"Failed to create OpenCode session ({resp.status_code}): {resp.text[:300]}"
            )
        body: dict[str, Any] = resp.json()
        session_id = body.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise MVPBuilderError("OpenCode session response missing 'id'")
        logger.info("OpenCode session created: %s", session_id)
        return session_id


async def send_message(
    session_id: str,
    text: str,
    *,
    agent: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Send a message to an OpenCode session and wait for the full response."""
    payload: dict[str, Any] = {
        "agent": agent or settings.OPENCODE_AGENT,
        "parts": [{"type": "text", "text": text}],
    }
    async with _client() as client:
        resp = await client.post(
            f"/session/{session_id}/message",
            json=payload,
            timeout=timeout or settings.MVP_BUILD_TIMEOUT,
        )
        if resp.status_code not in (200, 201):
            raise MVPBuilderError(
                f"OpenCode message failed ({resp.status_code}): {resp.text[:500]}"
            )
        result: dict[str, Any] = resp.json()
        return result


async def send_build_prompt(session_id: str, prompt: str) -> dict[str, Any]:
    """Send the MVP build prompt and wait for the full assistant response."""
    return await send_message(session_id, prompt)


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


def _compact(text: str | None, limit: int = 1400) -> str:
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
    modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])

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

    return "\n".join(
        [
            "# MVP Slot-Fill Request",
            "",
            f"**App:** {title} · **Industry:** {industry}",
            f"**Description:** {_compact(ai_state.get('business_description', ''), 600)}",
            f"**Modules:** {', '.join(map(str, modules))}",
            "",
            "A working scaffold already exists at `" + target_dir + "` (FastAPI backend, "
            "Next.js frontend, docker-compose, Render blueprint, CI workflow). "
            "Do NOT rewrite the scaffold. Fill the artifact-specific slots below and "
            "add the module code only.",
            "",
            "## What to implement",
            "1. **models.py** — one SQLAlchemy 2.0 async model per ER entity (insert above "
            "`__MODEL_INSERTION_POINT__`), matching the DDL exactly.",
            "2. **schemas.py** — Pydantic v2 create/read/update schemas for each model.",
            "3. **routers.py** — one APIRouter per module with full CRUD (insert above "
            "`__ROUTER_INSERTION_POINT__`) and register it in `main.py`.",
            "4. **demo auth** — keep the provided JWT helper; add a simple `auth/login` + "
            "`auth/register` endpoint if the API spec includes one.",
            "5. **frontend** — one CRUD page per module under `src/app/{module_slug}/`, a "
            "dashboard card per module in `src/app/page.tsx` (replace `__MODULE_LINKS__`), "
            "wired through the typed client in `src/lib/api.ts`.",
            "6. **Alembic** — one initial migration for the full schema.",
            "",
            "## Architecture context",
            f"HLD: {hld_overview or '_none provided_'}"
            + (
                f"\nLLD modules: {', '.join(str(m.get('name')) for m in lld_modules if isinstance(m, dict))}"
                if lld_modules
                else ""
            ),
            "",
            "## ER entities",
            _entity_summary(er) or "_none provided_",
            "",
            "## API spec",
            _endpoint_summary(api_spec) or "_none provided_",
            "",
            "## Wireframe screens",
            "\n".join(f"- {s}" for s in wireframe_screens) or "_none provided_",
            "",
            "## Database DDL",
            "```sql",
            ddl.strip() or "_none provided_",
            "```",
            "",
            "## Rules",
            "- Never hardcode secrets. `.env.example` uses `change-me` placeholders only.",
            "- Keep existing scaffold files intact unless a slot requires an edit.",
            "- Do not run installs, builds, or start servers — just edit files.",
            "- Report which modules/entities you implemented when finished.",
        ]
    )


# ── Build execution ────────────────────────────────────────────────────


async def run_build(
    solution_id: UUID,
    ai_state: dict[str, Any],
    build_number: int,
    *,
    title: str | None = None,
    check_npm: bool = True,
) -> dict[str, Any]:
    """Run an OpenCode MVP build synchronously. Returns build result metadata."""
    if not await health():
        raise MVPBuilderError(
            "OpenCode sidecar is unreachable. Ensure the opencode service is running."
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

    session_id = await create_session(f"MVP Build - {title or solution_id}")
    logger.info("Starting MVP build for solution=%s (session=%s)", solution_id, session_id)

    try:
        response = await send_build_prompt(session_id, prompt)
        logger.info(
            "MVP build finished for solution=%s (session=%s, %s)",
            solution_id,
            session_id,
            response.get("info") and response["info"].get("error", "ok"),
        )

        # Verification Checkpoint & Bounded Repair Turn
        from app.services.mvp_verifier import verify_and_repair

        await verify_and_repair(
            local_dir,
            session_id=session_id,
            target_dir=target_dir,
            send_prompt_fn=send_build_prompt,
            check_npm=check_npm,
        )
    except MVPBuilderError:
        await abort_session(session_id)
        raise
    except Exception:
        await abort_session(session_id)
        raise

    files = list_build_files(local_dir)
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


def build_bytes(build_dir: Path | str) -> bytes:
    """Zip the generated project into an in-memory buffer and return its bytes."""
    buffer = package_build(build_dir)
    return buffer.read()


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
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
                raise MVPBuilderError(f"Invalid env var name: {key!r}")
            # Strip line breaks so a malicious value can't inject extra
            # variables/commands into the generated .env.local file.
            safe_value = str(value).replace("\r", "").replace("\n", "")
            lines.append(f"{key}={safe_value}\n")
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
