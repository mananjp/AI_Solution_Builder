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
import contextlib
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


_working_opencode_url: str | None = None


def _candidate_urls() -> list[str]:
    candidates: list[str] = []
    configured = (settings.OPENCODE_SERVER_URL or "").strip().rstrip("/")
    # Filter out unreachable builder worker hostnames from legacy configs
    if configured and "ai-solution-builder-builder" not in configured:
        candidates.append(configured)
    for fallback in ("http://127.0.0.1:4096", "http://localhost:4096"):
        if fallback not in candidates:
            candidates.append(fallback)
    if configured and configured not in candidates:
        candidates.append(configured)
    return candidates


def _get_base_url() -> str:
    global _working_opencode_url
    if _working_opencode_url:
        return _working_opencode_url
    candidates = _candidate_urls()
    return candidates[0] if candidates else "http://127.0.0.1:4096"


def _client(base_url: str | None = None) -> httpx.AsyncClient:
    url = base_url or _get_base_url()
    return httpx.AsyncClient(
        base_url=url,
        headers=_auth_headers(),
        timeout=settings.MVP_BUILD_TIMEOUT,
    )


async def health() -> bool:
    """Check the OpenCode sidecar is reachable and healthy across candidate URLs."""
    global _working_opencode_url
    candidates = _candidate_urls()
    if _working_opencode_url and _working_opencode_url in candidates:
        candidates.remove(_working_opencode_url)
        candidates.insert(0, _working_opencode_url)

    for url in candidates:
        try:
            try:
                client_ctx = _client(base_url=url)
            except TypeError:
                client_ctx = _client()
            async with client_ctx as client:
                resp = await client.get("/global/health", timeout=3.0)
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("healthy", False):
                        if _working_opencode_url != url:
                            logger.info(
                                "OpenCode sidecar healthy at %s (version=%s)",
                                url,
                                body.get("version"),
                            )
                            _working_opencode_url = url
                        return True
        except Exception as exc:
            logger.debug("OpenCode candidate %s unreachable: %s", url, exc)

    logger.warning("OpenCode sidecar unreachable across candidates: %s", candidates)
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


def _auto_synthesize_slots(root: Path, ai_state: dict[str, Any], app_title: str) -> None:
    """Pre-populate models, schemas, routers, and UI slots from ER and API spec."""
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"
    if not backend_dir.exists():
        return

    er = (
        ai_state.get("er_diagram", {}).get("content", {})
        if isinstance(ai_state.get("er_diagram"), dict)
        else {}
    )
    entities = er.get("entities", []) if isinstance(er, dict) else []

    if not entities:
        modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])
        if modules:
            entities = [
                {
                    "name": re.sub(r"[^a-zA-Z0-9_]+", "_", str(m).lower()).strip("_"),
                    "fields": [{"name": "name", "type": "VARCHAR(255)"}],
                }
                for m in modules[:3]
            ]
        else:
            entities = [{"name": "item", "fields": [{"name": "title", "type": "VARCHAR(255)"}]}]

    model_chunks = []
    schema_chunks = []
    router_chunks = []
    card_chunks = []

    for ent in entities:
        if not isinstance(ent, dict):
            continue
        raw_name = ent.get("name") or "item"
        clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_name.lower()).strip("_")
        if not clean_name:
            continue
        class_name = "".join(part.capitalize() for part in clean_name.split("_"))

        # Model
        model_code = f"""class {class_name}(Base):
    __tablename__ = "{clean_name}"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Sample {class_name}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
"""
        model_chunks.append(model_code.strip())

        # Schema
        schema_code = f"""class {class_name}Base(BaseModel):
    name: str = "Sample {class_name}"


class {class_name}Create({class_name}Base):
    pass


class {class_name}Read({class_name}Base):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""
        schema_chunks.append(schema_code.strip())

        # Router
        router_code = f"""@router.get("/{clean_name}", response_model=list[schemas.{class_name}Read])
async def list_{clean_name}(session: SessionDep) -> list[models.{class_name}]:
    res = await session.execute(select(models.{class_name}).order_by(models.{class_name}.created_at.desc()).limit(100))
    return list(res.scalars().all())


@router.post("/{clean_name}", response_model=schemas.{class_name}Read, status_code=201)
async def create_{clean_name}(payload: schemas.{class_name}Create, session: SessionDep) -> models.{class_name}:
    obj = models.{class_name}(name=payload.name)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.delete("/{clean_name}/{{item_id}}")
async def delete_{clean_name}(item_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:
    obj = await session.get(models.{class_name}, item_id)
    if obj:
        await session.delete(obj)
        await session.commit()
    return {{"ok": True}}
"""
        router_chunks.append(router_code.strip())

        card_code = f"""          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 shadow-sm">
            <h3 className="text-base font-bold text-slate-800">{class_name} Module</h3>
            <p className="mt-1 text-xs text-slate-500">Autonomous CRUD service endpoint: <code>/api/v1/{clean_name}</code></p>
            <span className="mt-3 inline-block rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-600 border border-indigo-100">
              Active Endpoint
            </span>
          </div>"""
        card_chunks.append(card_code)

    # Apply to models.py
    models_file = backend_dir / "models.py"
    if models_file.exists():
        content = models_file.read_text(encoding="utf-8")
        if "# __MODEL_INSERTION_POINT__" in content and model_chunks:
            imports = "import uuid\nfrom datetime import UTC, datetime\nfrom sqlalchemy import DateTime, String\nfrom sqlalchemy.dialects.postgresql import UUID\nfrom sqlalchemy.orm import Mapped, mapped_column\n\n"
            replacement = imports + "\n\n".join(model_chunks) + "\n\n# __MODEL_INSERTION_POINT__"
            models_file.write_text(
                content.replace("# __MODEL_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to schemas.py
    schemas_file = backend_dir / "schemas.py"
    if schemas_file.exists():
        content = schemas_file.read_text(encoding="utf-8")
        if "# __SCHEMA_INSERTION_POINT__" in content and schema_chunks:
            imports = "import uuid\nfrom datetime import datetime\nfrom pydantic import BaseModel, ConfigDict\n\n"
            replacement = imports + "\n\n".join(schema_chunks) + "\n\n# __SCHEMA_INSERTION_POINT__"
            schemas_file.write_text(
                content.replace("# __SCHEMA_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to routers.py
    routers_file = backend_dir / "routers.py"
    if routers_file.exists():
        content = routers_file.read_text(encoding="utf-8")
        if "# __ROUTER_INSERTION_POINT__" in content and router_chunks:
            imports = (
                "import uuid\nfrom sqlalchemy import select\n"
                "try:\n    from . import models, schemas\n"
                "except (ImportError, ValueError):\n    import models, schemas\n\n"
            )
            replacement = imports + "\n\n".join(router_chunks) + "\n\n# __ROUTER_INSERTION_POINT__"
            routers_file.write_text(
                content.replace("# __ROUTER_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to frontend page.tsx
    page_file = frontend_dir / "src" / "app" / "page.tsx"
    if page_file.exists():
        content = page_file.read_text(encoding="utf-8")
        if "{/* __MODULE_LINKS__ */}" in content and card_chunks:
            page_file.write_text(
                content.replace("{/* __MODULE_LINKS__ */}", "\n".join(card_chunks)),
                encoding="utf-8",
            )


def scaffold_build(
    build_dir: Path | str,
    *,
    app_title: str,
    inject_modules: list[str],
    ai_state: dict[str, Any] | None = None,
) -> None:
    """Seed a build directory by copying the scaffold template.

    Copies the bundled template into `build_dir`, substitutes deterministic
    placeholders (app name/title/slug, JWT secret) and pre-populates
    models, schemas, and routers from the solution's ER diagram so the app
    is immediately functional and verified.
    """
    root = Path(build_dir)
    shutil.copytree(template_root(), root, dirs_exist_ok=True, ignore=_ignore_artifacts)

    # Ensure root has render.yaml, README.md, docker-compose.yml for Render Blueprint & GitHub
    infra_dir = root / "infra"
    if infra_dir.exists():
        for filename in ("render.yaml", "docker-compose.yml", "README.md"):
            src = infra_dir / filename
            dst = root / filename
            if src.exists() and not dst.exists():
                shutil.copyfile(src, dst)
        infra_gh = infra_dir / ".github"
        root_gh = root / ".github"
        if infra_gh.exists() and not root_gh.exists():
            shutil.copytree(infra_gh, root_gh, dirs_exist_ok=True)

    # Ensure frontend/src/lib/api.ts and public/.gitkeep always exist for frontend builds
    frontend_dir = root / "frontend"
    if frontend_dir.exists():
        lib_dir = frontend_dir / "src" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        api_ts = lib_dir / "api.ts"
        if not api_ts.exists():
            from app.services.templates import _API_CLIENT_TS

            api_ts.write_text(_API_CLIENT_TS, encoding="utf-8")
        pub_dir = frontend_dir / "public"
        pub_dir.mkdir(parents=True, exist_ok=True)
        (pub_dir / ".gitkeep").touch()

    app_name = _slugify(app_title)
    db_name = re.sub(r"[^a-z0-9_]+", "_", app_name).strip("_") or "app_db"
    mapping = {
        "APP_NAME": app_name,
        "APP_TITLE": app_title,
        "APP_SLUG": app_name,
        "APP_DB_NAME": db_name,
        "JWT_SECRET": "change-me-generated-jwt-secret",
    }

    # Apply substitutions to all text files carrying placeholders.
    _substitute_tree(root, mapping)

    # Pre-populate slots from ai_state if available for immediate validity
    if ai_state:
        try:
            _auto_synthesize_slots(root, ai_state, app_title)
        except Exception as exc:
            logger.warning("Auto slot synthesis skipped: %s", exc)

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
    check_npm: bool = False,
    allow_offline: bool = False,
) -> dict[str, Any]:
    """Run an OpenCode MVP build synchronously. Returns build result metadata."""
    if not allow_offline and not await health():
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
        ai_state=ai_state,
    )

    prompt = build_mvp_prompt(ai_state, target_dir, app_title=title)

    session_id: str = "auto-synthesized"
    sidecar_ok = await health()
    if sidecar_ok:
        try:
            session_id = await create_session(f"MVP Build - {title or solution_id}")
            logger.info("Starting MVP build for solution=%s (session=%s)", solution_id, session_id)
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
        except Exception as exc:
            logger.warning(
                "OpenCode refinement failed or timed out (%s); relying on auto-synthesized scaffold for solution=%s",
                exc,
                solution_id,
            )
            if session_id and session_id != "auto-synthesized":
                with contextlib.suppress(Exception):
                    await abort_session(session_id)
    else:
        logger.info(
            "OpenCode sidecar offline; build synthesized instantly from blueprint for solution=%s",
            solution_id,
        )

    files = list_build_files(local_dir)
    return {
        "session_id": session_id,
        "local_dir": str(local_dir),
        "file_count": len(files),
        "files": relative_paths(local_dir),
    }


async def run_premade_build(
    solution_id: UUID,
    template_slug: str,
    build_number: int,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    """Instantly build a starter template without LLM roundtrip latency."""
    from app.services import templates

    local_dir = build_workspace_dir(solution_id, build_number)
    app_title = title or template_slug.title()

    # 1. Base scaffold
    scaffold_build(
        local_dir,
        app_title=app_title,
        inject_modules=[template_slug],
    )

    # 2. Instantiate pre-generated, production-ready template files
    templates.apply_template_files(local_dir, template_slug, app_title=app_title)

    logger.info(
        "Instant premade MVP build complete for solution=%s (template=%s)",
        solution_id,
        template_slug,
    )
    files = list_build_files(local_dir)
    return {
        "session_id": f"premade-{template_slug}",
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
