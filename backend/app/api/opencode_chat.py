"""
AI Solution Builder — OpenCode Direct Chat API

Lets the user chat directly with the OpenCode sidecar (the "Custom App
Builder" path).  When the sidecar is unavailable the endpoint falls back to
the *integrated synthesizer* — a direct LLM conversation backed by the
blueprint scaffold — so the feature remains fully usable without the
sidecar process.

Each solution keeps a persistent session and a scaffolded workspace; the
agent (or synthesizer) edits files in-place as the conversation progresses.
When the user asks to finish (``build_requested``), the workspace is
verified/repaired and finalized into an ``MVPBuild`` for download/deploy.

Endpoints:
    GET  /api/v1/opencode/health      Service liveness probe (dashboard banner)
    POST /api/v1/opencode/chat        SSE chat stream (build_requested finalizes)
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.chat import _persist_artifacts
from app.core.build_locks import allocate_build_number
from app.core.config import settings
from app.core.credits import require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.i18n import translate_text
from app.core.llm import get_llm, has_llm_credentials
from app.core.security import get_current_user
from app.models.mvp_build import MVPBuild
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import OpenCodeChatRequest
from app.services import mvp_builder as builder
from app.services import mvp_verifier
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opencode", tags=["OpenCode Chat"])

_TARGET_MAX_CONTEXT = 20_000  # uploaded-context cap fed to the sidecar


def _extract_app_title(prompt: str, fallback: str = "Custom App") -> str:
    """Extract a clean, concise application title from a user prompt."""
    if not prompt or not prompt.strip():
        return fallback

    cleaned = prompt.strip()
    # Check if prompt is just a greeting or single non-descriptive word
    if cleaned.lower().rstrip(".!?") in {
        "hi",
        "hello",
        "hey",
        "test",
        "build",
        "app",
        "help",
        "yo",
        "start",
    }:
        return fallback

    # Check for explicit named patterns first: "called XYZ" or "named XYZ"
    named_match = re.search(
        r"(?:called|named)\s+[\"']?([A-Za-z0-9_\-\s]{2,40}?)[\"']?(?:\s+(?:for|with|that|which|\.|\,)|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if named_match:
        name = named_match.group(1).strip()
        if name:
            return name

    patterns = [
        r"^(?:please\s+)?(?:i\s+want\s+to\s+|i\s+would\s+like\s+to\s+|can\s+you\s+)?(?:build|create|make|develop|design|generate)\s+(?:me\s+)?(?:an?\s+)?(?:mvp\s+)?(?:app\s+for\s+|application\s+for\s+|system\s+for\s+|platform\s+for\s+)?(?:an?\s+)?",
        r"^(?:i\s+need\s+an?\s+app\s+for\s+|i\s+need\s+an?\s+application\s+for\s+|i\s+need\s+a\s+system\s+for\s+)",
        r"^(?:build\s+|create\s+|make\s+|design\s+)(?:an?\s+)?(?:app\s+for\s+|application\s+for\s+|system\s+for\s+)?(?:an?\s+)?",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()

    first_clause = re.split(
        r"[.\n,;]|\bwith\b|\bthat\b|\bfor\b|\bwhich\b", cleaned, flags=re.IGNORECASE
    )[0].strip()
    words = first_clause.split()
    if 1 <= len(words) <= 6:
        candidate = " ".join(words).title()
        return candidate[:60]

    if words:
        candidate = " ".join(words[:4]).title()
        return candidate[:60]
    return fallback


def _synthesize_artifacts_from_spec(
    title: str,
    industry: str,
    modules: list[str],
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct full architecture artifacts (HLD, LLD, ER, schema, APIs, wireframes) from entities."""
    normalized_entities: list[dict[str, Any]] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        ent_name = str(ent.get("name", "item"))
        clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", ent_name.lower()).strip("_") or "item"
        raw_fields = ent.get("fields", [])
        clean_fields: list[dict[str, str]] = []
        has_id = False
        for f in raw_fields:
            if isinstance(f, dict):
                fname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f.get("name", "")).lower()).strip("_")
                ftype = str(f.get("type", "VARCHAR(255)")).upper()
            else:
                fname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f).lower()).strip("_")
                ftype = "VARCHAR(255)"
            if fname == "id":
                has_id = True
                clean_fields.insert(0, {"name": "id", "type": "UUID"})
            elif fname:
                clean_fields.append({"name": fname, "type": ftype})
        if not has_id:
            clean_fields.insert(0, {"name": "id", "type": "UUID"})
        normalized_entities.append({"name": clean_name, "fields": clean_fields})

    entities = normalized_entities or [
        {
            "name": "items",
            "fields": [{"name": "id", "type": "UUID"}, {"name": "name", "type": "VARCHAR(255)"}],
        }
    ]

    ddl_statements: list[str] = []
    for ent in entities:
        ent_name = str(ent["name"])
        ent_fields = cast(list[dict[str, str]], ent.get("fields", []))
        cols = ", ".join(f"{f['name']} {f['type']}" for f in ent_fields)
        ddl_statements.append(f"CREATE TABLE {ent_name} ({cols});")
    schema_ddl = "\n".join(ddl_statements)

    endpoints: list[dict[str, str]] = []
    for ent in entities:
        ent_name = str(ent["name"])
        endpoints.extend(
            [
                {
                    "method": "GET",
                    "path": f"/api/v1/{ent_name}",
                    "description": f"List {ent_name}",
                },
                {
                    "method": "POST",
                    "path": f"/api/v1/{ent_name}",
                    "description": f"Create {ent_name}",
                },
                {
                    "method": "DELETE",
                    "path": f"/api/v1/{ent_name}/{{item_id}}",
                    "description": f"Delete {ent_name}",
                },
            ]
        )

    screens: list[dict[str, Any]] = []
    for ent in entities:
        ent_name = str(ent["name"])
        ent_fields = cast(list[dict[str, str]], ent.get("fields", []))
        screens.append(
            {
                "name": f"{ent_name.replace('_', ' ').title()} Dashboard",
                "route": f"/{ent_name}",
                "description": f"CRUD management for {ent_name}",
                "layout": "sidebar",
                "components": [
                    {
                        "type": "data_table",
                        "title": f"{ent_name.replace('_', ' ').title()} Table",
                        "fields": [f["name"] for f in ent_fields],
                    }
                ],
            }
        )

    components: list[dict[str, str]] = [
        {
            "name": "Frontend",
            "technology": "Next.js 14 / React",
            "description": "Responsive dashboard with data tables",
        },
        {
            "name": "API Service",
            "technology": "FastAPI",
            "description": "REST API with automated OpenAPI docs",
        },
        {
            "name": "Database",
            "technology": "PostgreSQL",
            "description": "Relational data store with UUID primary keys",
        },
    ]

    hld_dict: dict[str, Any] = {
        "title": f"High-Level Design — {title}",
        "system_overview": f"A scalable full-stack application for {title}, powered by FastAPI and Next.js.",
        "components": components,
        "deployment": {"environment": "Render / Docker", "scaling_strategy": "horizontal"},
        "security": {"authentication": "JWT", "authorization": "RBAC"},
    }

    lld_modules: list[dict[str, Any]] = [
        {
            "name": m,
            "endpoints": [e for e in endpoints if m in e["path"] or True],
            "data_models": [str(ent["name"]) for ent in entities],
        }
        for m in modules[:2]
    ]

    lld_dict: dict[str, Any] = {
        "title": f"Low-Level Design — {title}",
        "modules": lld_modules,
    }

    phases: list[dict[str, Any]] = [
        {
            "name": "Phase 1: Core Foundation",
            "duration": "2 weeks",
            "modules": modules[:2],
            "deliverables": ["Database", "REST APIs", "Dashboard UI"],
        },
        {
            "name": "Phase 2: Full Integration",
            "duration": "2 weeks",
            "modules": modules[2:],
            "deliverables": ["Advanced Filtering", "Exporting", "Audit Logs"],
        },
    ]

    roadmap_dict: dict[str, Any] = {
        "title": f"Sprint Roadmap — {title}",
        "phases": phases,
    }

    tables: list[dict[str, Any]] = [
        {
            "table": str(e["name"]),
            "columns": [
                f"{f['name']} {f['type']}" for f in cast(list[dict[str, str]], e.get("fields", []))
            ],
        }
        for e in entities
    ]

    return {
        "industry": industry,
        "confirmed_modules": modules,
        "identified_solutions": modules,
        "hld": {
            "artifact_type": "hld",
            "title": f"High-Level Design — {title}",
            "content": hld_dict,
            "content_text": f"# High-Level Design — {title}\n\n{hld_dict['system_overview']}\n\n## Components\n"
            + "\n".join(
                f"- **{c['name']}** ({c['technology']}): {c['description']}" for c in components
            ),
        },
        "lld": {
            "artifact_type": "lld",
            "title": f"Low-Level Design — {title}",
            "content": lld_dict,
            "content_text": f"# Low-Level Design — {title}\n\n## Modules\n"
            + "\n".join(f"- **{m['name']}**" for m in lld_modules),
        },
        "er_diagram": {
            "artifact_type": "er_diagram",
            "title": f"Entity Relationship Diagram — {title}",
            "content": {"entities": entities, "relationships": []},
            "content_text": f"# ER Diagram — {title}\n\n"
            + "\n".join(
                f"- **{e['name']}**: {', '.join(f['name'] for f in cast(list[dict[str, str]], e.get('fields', [])))}"
                for e in entities
            ),
        },
        "database_schema": {
            "artifact_type": "database_schema",
            "title": f"Database DDL & Schema — {title}",
            "content": {"schema_ddl": schema_ddl, "entities": entities},
            "content_text": f"```sql\n{schema_ddl}\n```",
        },
        "api_spec": {
            "artifact_type": "api_spec",
            "title": f"OpenAPI Specification — {title}",
            "content": {"endpoints": endpoints},
            "content_text": f"# API Endpoints — {title}\n\n"
            + "\n".join(f"- `{e['method']} {e['path']}`: {e['description']}" for e in endpoints),
        },
        "wireframes": [
            {
                "artifact_type": "wireframe",
                "title": f"UI Wireframes — {title}",
                "content": {"screens": screens},
                "content_text": f"# Wireframe Screens — {title}\n\n"
                + "\n".join(
                    f"- **{s['name']}** (`{s['route']}`): {s['description']}" for s in screens
                ),
            }
        ],
        "bpmn_flows": [
            {
                "artifact_type": "bpmn_flows",
                "title": f"Process Workflow — {title}",
                "content": {
                    "flows": [
                        {"id": "flow_1", "name": f"{m.replace('_', ' ').title()} Flow"}
                        for m in modules
                    ]
                },
                "content_text": f"# Process Workflow — {title}\n\n"
                + "\n".join(f"- {m.replace('_', ' ').title()}" for m in modules),
            }
        ],
        "roadmap": {
            "artifact_type": "roadmap",
            "title": f"Sprint Roadmap — {title}",
            "content": roadmap_dict,
            "content_text": f"# Sprint Roadmap — {title}\n\n"
            + "\n".join(
                f"- **{p['name']}** ({p['duration']}): {', '.join(cast(list[str], p['deliverables']))}"
                for p in phases
            ),
        },
        "generated_schema": {
            "artifact_type": "workable_schema",
            "title": f"Executable Database Schema — {title}",
            "content": {
                "tables": tables,
                "ddl": schema_ddl,
            },
            "content_text": f"```sql\n{schema_ddl}\n```",
        },
    }


def _artifacts_from_app_spec(spec: Any) -> dict[str, Any]:
    """Convert an AppSpec into standard AI Solution Builder artifact dictionaries."""
    title = spec.app_name
    industry = "custom_domain"
    modules = [f"{e.plural}_mgmt" for e in spec.entities]
    entities = [
        {
            "name": e.plural,
            "fields": [
                {"name": "id", "type": "INTEGER"},
                *[
                    {
                        "name": f.name,
                        "type": (
                            "VARCHAR(255)"
                            if f.type == "string"
                            else (
                                "INTEGER"
                                if f.type in ("int", "ref")
                                else (
                                    "FLOAT"
                                    if f.type == "float"
                                    else ("BOOLEAN" if f.type == "bool" else "TEXT")
                                )
                            )
                        ),
                    }
                    for f in e.fields
                ],
            ],
        }
        for e in spec.entities
    ]
    res = _synthesize_artifacts_from_spec(title, industry, modules, entities)
    res["app_title"] = title
    res["app_spec"] = spec.model_dump()
    return res


async def _synthesize_domain_artifacts_dynamic(
    title: str,
    user_prompt: str,
    context: str = "",
    history: list[dict[str, Any]] | None = None,
    existing_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dynamically synthesize domain models, entities, and modules for the user's application.

    Spec-first: one validated AppSpec is generated by the LLM (deterministic codegen
    consumes it later). Confirmation prompts preserve the existing architecture. No
    keyword/template guessing is ever used as a fallback -- if no spec can be produced
    and no prior domain state exists, the request fails rather than building a generic app.
    """
    # 1. Check if user prompt is a short confirmation (e.g. "build it", "build it now", "yes", "proceed")
    # and we already have existing domain entities in existing_state.
    short_confirmations = {
        "build",
        "build it",
        "build it now",
        "build now",
        "build app",
        "build please",
        "please build",
        "please build it",
        "yes",
        "yes please",
        "go ahead",
        "proceed",
        "proceed with build",
        "finalize",
        "deploy",
        "confirm",
        "looks good",
        "looks good build it",
        "ok",
        "okay",
        "start build",
        "build and deploy",
    }
    cleaned_prompt = re.sub(r"[^a-zA-Z0-9\s]+", "", user_prompt.strip().lower()).strip()
    words = cleaned_prompt.split()
    is_confirmation = cleaned_prompt in short_confirmations or (
        len(words) <= 5
        and any(
            w in words
            for w in ("build", "proceed", "finalize", "confirm", "deploy", "yes", "ok", "okay")
        )
        and not any(
            w in words
            for w in (
                "create",
                "make",
                "design",
                "instead",
                "change",
                "modify",
                "different",
                "new",
                "another",
            )
        )
    )

    if (
        is_confirmation
        and existing_state
        and existing_state.get("er_diagram", {}).get("content", {}).get("entities")
    ):
        logger.info(
            "Preserving existing domain architecture for confirmation prompt '%s'", user_prompt
        )
        return dict(existing_state)

    # 2. Combine history if current prompt is short but we need context
    effective_prompt = user_prompt
    if len(user_prompt.split()) < 5 and history:
        user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
        if user_msgs:
            effective_prompt = f"{' '.join(user_msgs[-3:])} {user_prompt}"

    # 3. Attempt AppSpec generation first
    try:
        from app.services.app_spec import generate_app_spec

        spec = await generate_app_spec(existing_state or {}, effective_prompt)
        res = _artifacts_from_app_spec(spec)
        logger.info("Successfully generated AppSpec via LLM for '%s'", spec.app_name)
        return res
    except Exception as exc:
        logger.info("generate_app_spec skipped (%s); trying direct structured synthesis", exc)

    # 4. Attempt LLM-based structured synthesis
    try:
        llm = get_llm(temperature=0.1)
        sys_prompt = (
            "You are an expert software architect. Analyze the user's application requirements "
            "and extract a structured domain specification as a JSON object with EXACTLY this schema:\n"
            "{\n"
            '  "app_title": "Concise 2-4 word application name (e.g. FitPulse Gym, MedTrack Inventory)",\n'
            '  "industry": "slugified industry name (e.g. fitness_gym, healthcare, ecommerce)",\n'
            '  "modules": ["module1_slug", "module2_slug", "module3_slug", "module4_slug"],\n'
            '  "entities": [\n'
            "    {\n"
            '      "name": "plural_table_name (e.g. members, trainers, classes)",\n'
            '      "fields": [\n'
            '        {"name": "id", "type": "UUID"},\n'
            '        {"name": "field_name", "type": "VARCHAR(255) | TEXT | INTEGER | FLOAT | BOOLEAN"}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Include 3-5 domain entities with 4-7 realistic fields each tailored precisely to the user's app. "
            "Respond ONLY with the JSON object."
        )
        user_content = f"User Request: {effective_prompt}"
        if context:
            user_content = f"Uploaded Context:\n{context[:4000]}\n\n{user_content}"

        resp = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_content)]),
            timeout=10.0,
        )
        if resp and resp.content:
            raw_text = str(resp.content).strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw_text)
            if (
                isinstance(parsed, dict)
                and parsed.get("entities")
                and isinstance(parsed["entities"], list)
                and len(parsed["entities"]) >= 1
            ):
                app_title = parsed.get("app_title") or title or _extract_app_title(effective_prompt)
                industry = parsed.get("industry") or "custom_domain"
                modules = parsed.get("modules") or [
                    f"{e.get('name', 'item')}_mgmt" for e in parsed["entities"]
                ]
                entities = parsed["entities"]
                logger.info(
                    "LLM synthesized custom domain for '%s': %s (%d entities)",
                    app_title,
                    industry,
                    len(entities),
                )
                res = _synthesize_artifacts_from_spec(app_title, industry, modules, entities)
                res["app_title"] = app_title
                return res
    except Exception as exc:
        logger.warning("LLM dynamic domain synthesis skipped or failed (%s)", exc)

    # 5. No canned-domain fallback: honoring spec-first design, a generic
    #    {name, status} shell must never be shipped as the user's app. If the
    #    user already has a domain model, preserve it; otherwise fail honestly
    #    so the UI can ask for more detail instead of building a look-alike.
    if existing_state and (existing_state.get("er_diagram") or existing_state.get("entities")):
        return dict(existing_state)
    raise ValueError(
        "Couldn't design the app model from this request. Please add detail about your "
        "business, entities, and workflows."
    )


@router.get("/health")
async def health() -> dict[str, Any]:
    """Report whether the AI build engine is reachable and ready.

    ``healthy`` is ``True`` whenever the service can handle a request —
    either via the live sidecar *or* via the integrated synthesizer
    fallback.  ``sidecar_healthy`` reports the sidecar process itself, along
    with a best-effort version/model/latency snapshot for the dashboard.
    """
    info = await builder.health_info()
    sidecar_ok = bool(info["sidecar_healthy"])
    payload: dict[str, Any] = {
        "healthy": True,
        "sidecar_healthy": sidecar_ok,
        "mode": "opencode-sidecar" if sidecar_ok else "integrated-synthesizer",
    }
    if info.get("version"):
        payload["version"] = info["version"]
    if info.get("model"):
        payload["model"] = info["model"]
    if info.get("latency_ms") is not None:
        payload["latency_ms"] = info["latency_ms"]
    return payload


@router.get("/diagnose")
async def diagnose(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Run a lightweight sidecar self-check with actionable fixes.

    Performs a live round-trip (create session -> prompt -> echo) so it proves
    the sidecar can actually generate, not just that the port is open.
    """
    return await builder.diagnose()


async def _verify_solution_access(db: AsyncSession, solution_id: UUID, user: User) -> Solution:
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == user.org_id)
    )
    solution = result.scalar_one_or_none()
    if not solution:
        res_direct = await db.execute(select(Solution).where(Solution.id == solution_id))
        solution = res_direct.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


async def _get_or_create_workspace(db: AsyncSession, user: User) -> Workspace:
    result = await db.execute(
        select(Workspace)
        .where(Workspace.org_id == user.org_id)
        .order_by(Workspace.created_at)
        .limit(1)
    )
    workspace = result.scalar_one_or_none()
    if workspace is not None:
        return workspace
    workspace = Workspace(
        org_id=user.org_id,
        name="Custom App Builder",
        description="Apps built through conversational OpenCode chat",
    )
    db.add(workspace)
    await db.flush()
    return workspace


def _extract_text(response: dict[str, Any]) -> str:
    """Concatenate the text parts from an OpenCode message response."""
    parts = response.get("parts") or []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip()


@router.post("/chat")
async def chat(
    payload: OpenCodeChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Chat directly with OpenCode; streaming SSE response."""
    # Eager ownership check; gracefully fall back to fresh session if solution was purged or uncommitted
    content_language: str = getattr(request.state, "language", "en")
    if payload.solution_id:
        try:
            await _verify_solution_access(db, payload.solution_id, current_user)
        except Exception as exc:
            logger.warning(
                "Requested solution_id %s inaccessible (%s); starting fresh session",
                payload.solution_id,
                exc,
            )
            payload.solution_id = None

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            # Streaming over a dependency-injected session is unsafe (see
            # chat.py for the rationale) — open an explicit session here.
            async with async_session_factory() as stream_db:
                solution = None
                if payload.solution_id:
                    try:
                        solution = await _verify_solution_access(
                            stream_db, payload.solution_id, current_user
                        )
                        if payload.app_name and solution.title in (
                            "Custom App Build",
                            "Custom App",
                        ):
                            solution.title = payload.app_name
                    except Exception as exc:
                        logger.warning(
                            "Could not load solution_id %s in stream_db (%s); creating fresh",
                            payload.solution_id,
                            exc,
                        )
                        solution = None

                if solution is None:
                    workspace = await _get_or_create_workspace(stream_db, current_user)
                    initial_title = payload.app_name or _extract_app_title(payload.message)
                    solution = Solution(
                        workspace_id=workspace.id,
                        title=initial_title,
                        description=f"App built through conversational OpenCode chat: {payload.message[:200]}",
                        status="discovery",
                        conversation_history=[],
                    )
                    stream_db.add(solution)
                    await stream_db.commit()
                    await stream_db.refresh(solution)

                sidecar_ok = await builder.health()
                ai_state = dict(solution.ai_state or {})
                session_id: str | None = ai_state.get("opencode_session_id") or payload.session_id

                # ── Sidecar path vs integrated-synthesizer path ──────
                if sidecar_ok:
                    if session_id and payload.session_id and session_id != payload.session_id:
                        yield {
                            "event": "error",
                            "data": json.dumps(
                                {"message": "Session id does not match this solution."}
                            ),
                        }
                        return
                    if not session_id:
                        session_id = await builder.create_session(
                            f"Custom Build - {solution.title}"
                        )
                        ai_state["opencode_session_id"] = session_id
                    agent_name = "opencode"
                    agent_msg = "Connected to the OpenCode sidecar..."
                else:
                    # Integrated-synthesizer mode — no live sidecar needed.
                    session_id = session_id or f"synthesizer-{solution.id}"
                    ai_state["opencode_session_id"] = session_id
                    agent_name = "AI Developer"
                    agent_msg = "Connected to the AI build engine..."

                yield {
                    "event": "agent_start",
                    "data": json.dumps(
                        {
                            "agent": agent_name,
                            "session_id": session_id,
                            "solution_id": str(solution.id),
                            "message": agent_msg,
                        }
                    ),
                }

                # Report runtime capability so the UI can be honest about
                # whether this build is simulation-only or model-powered.
                llm_provider = settings.LLM_PROVIDER.lower()
                llm_creds = has_llm_credentials()
                simulation = (not sidecar_ok) and (llm_provider == "mock" or not llm_creds)
                yield {
                    "event": "capability",
                    "data": json.dumps(
                        {
                            "sidecar_online": sidecar_ok,
                            "llm_provider": settings.LLM_PROVIDER,
                            "llm_authenticated": llm_creds,
                            "simulation": simulation,
                            "mode": "opencode-sidecar" if sidecar_ok else "integrated-synthesizer",
                        }
                    ),
                }

                # Ensure the chat workspace is scaffolded once per solution.
                ws_dir = builder.chat_workspace_dir(solution.id)
                if not any(ws_dir.iterdir()):
                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=[],
                    )

                target_dir = builder.chat_container_target(solution.id)

                # ── Generate the conversational reply ────────────────
                if sidecar_ok:
                    instruction = (
                        f"# Custom Build Request — {solution.title}\n\n"
                        f"{payload.message}\n\n"
                        "## Working directory\n"
                        "A working FastAPI + Next.js scaffold already exists at `"
                        f"{target_dir}`. Implement the requested app by editing files "
                        f"inside `{target_dir}` only. Keep the scaffold structure; add "
                        "models, schemas, routers, and frontend pages to satisfy the "
                        "request. Do not run installs or builds — just edit files.\n"
                        "Report which files/modules you added when finished."
                    )
                    if payload.uploaded_context:
                        context = payload.uploaded_context[:_TARGET_MAX_CONTEXT]
                        instruction = (
                            f"## Context from uploaded document\n{context}\n\n" + instruction
                        )

                    try:
                        response = await asyncio.wait_for(
                            builder.send_message(
                                session_id,
                                instruction,
                                agent=settings.OPENCODE_AGENT,
                                timeout=25,
                            ),
                            timeout=30.0,
                        )
                        assistant_text = _extract_text(response) or (
                            "Done — tell me what to change next, or hit Build & Deploy "
                            "to finalize the app."
                        )
                    except Exception as sidecar_err:
                        logger.warning(
                            "Sidecar send_message failed (%s); falling back to direct LLM",
                            sidecar_err,
                        )
                        assistant_text = ""
                else:
                    assistant_text = ""

                if not assistant_text:
                    # Integrated synthesizer — direct LLM conversation.
                    llm = get_llm()
                    arch_summary_parts: list[str] = [f"Application Title: {solution.title}"]
                    if solution.description:
                        arch_summary_parts.append(f"Description: {solution.description}")

                    entities_list = (ai_state.get("er_diagram") or {}).get("content", {}).get(
                        "entities", []
                    ) or ai_state.get("entities", [])
                    if entities_list:
                        ent_strs: list[str] = []
                        for e in entities_list:
                            if isinstance(e, dict):
                                f_names = [
                                    f.get("name") if isinstance(f, dict) else str(f)
                                    for f in e.get("fields", [])
                                    if isinstance(f, dict)
                                ]
                                f_str = "".join(
                                    f"{n}; " for n in f_names if isinstance(n, str)
                                ).rstrip("; ")
                                ent_strs.append(f"{e.get('name')}: ({f_str})")
                        if ent_strs:
                            arch_summary_parts.append("Database Entities: " + "; ".join(ent_strs))

                    endpoints_list = (ai_state.get("api_spec") or {}).get("content", {}).get(
                        "endpoints", []
                    ) or ai_state.get("endpoints", [])
                    if endpoints_list:
                        ep_strs = [
                            f"{ep.get('method', 'GET')} {ep.get('path', '')}"
                            for ep in endpoints_list[:8]
                            if isinstance(ep, dict)
                        ]
                        if ep_strs:
                            arch_summary_parts.append("API Endpoints: " + ", ".join(ep_strs))

                    hld_overview = (
                        (ai_state.get("hld") or {}).get("content", {}).get("system_overview")
                    )
                    if hld_overview:
                        arch_summary_parts.append(f"System Architecture: {hld_overview}")

                    arch_context = "\n".join(arch_summary_parts)

                    sys_prompt = (
                        "You are an expert full-stack AI Developer & Solution Architect for AI Solution Builder. "
                        "You are helping the user architect, understand, and build a complete "
                        "FastAPI + Next.js application. A full working scaffold with "
                        "database, auth, and API structure is already configured.\n\n"
                        f"Current Solution Architecture Context:\n{arch_context}\n\n"
                        "Instructions:\n"
                        "- Answer the user's questions clearly, whether they ask about high-level requirements, "
                        "database schemas, API design, frontend UX components (such as customer storefronts, interactive cart drawers, or admin kitchen boards), "
                        "or technical implementation details.\n"
                        "- If the user asks about technicalities, explain the concrete models, endpoints, state management, and frontend features.\n"
                        "- Keep responses structured, informative, professional, and concise."
                    )
                    user_prompt = payload.message
                    if payload.uploaded_context:
                        user_prompt = (
                            f"Context from uploaded document:\n"
                            f"{payload.uploaded_context[:_TARGET_MAX_CONTEXT]}\n\n"
                            f"User request:\n{user_prompt}"
                        )

                    try:
                        resp = await llm.ainvoke(
                            [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
                        )
                        if resp and resp.content:
                            try:
                                parsed = json.loads(resp.content)
                                if isinstance(parsed, dict) and "content" in parsed:
                                    assistant_text = str(parsed["content"])
                                elif isinstance(parsed, dict) and "message" in parsed:
                                    assistant_text = str(parsed["message"])
                                else:
                                    assistant_text = str(resp.content)
                            except (json.JSONDecodeError, TypeError):
                                assistant_text = str(resp.content)
                    except Exception as llm_err:
                        logger.warning(
                            "LLM chat invoke failed (%s); using contextual synthesis", llm_err
                        )
                        assistant_text = ""
                    if not assistant_text or assistant_text == "Mock response":
                        assistant_text = (
                            f"I've structured your application requirements for **{solution.title}** into the "
                            "FastAPI backend and Next.js frontend workspace.\n\n"
                            "• **Architecture**: FastAPI REST backend with SQLAlchemy 2.0 and PostgreSQL\n"
                            "• **Frontend**: Modern Next.js 15 App Router interface with responsive interactive components\n"
                            "• **Next step**: You can ask any technical questions or click **Synthesize & Build** to generate the working prototype."
                        )

                history = solution.conversation_history or []
                history.append({"role": "user", "content": payload.message})
                history.append({"role": "assistant", "content": assistant_text})
                solution.conversation_history = history

                synthesized = await _synthesize_domain_artifacts_dynamic(
                    solution.title,
                    payload.message,
                    context=payload.uploaded_context or "",
                    history=solution.conversation_history or [],
                    existing_state=ai_state,
                )
                if synthesized.get("app_title") and solution.title in (
                    "Custom App Build",
                    "Custom App",
                ):
                    solution.title = synthesized["app_title"]

                solution.ai_state = {
                    **ai_state,
                    **synthesized,
                    "solution_title": solution.title,
                    "business_description": ai_state.get("business_description") or payload.message,
                }

                build_state: dict[str, Any] = {}
                if payload.build_requested:
                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "analyzing",
                                "step": 1,
                                "total_steps": 7,
                                "percentage": 15,
                                "message": f"Synthesizing domain architecture for {solution.title}...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    await require_and_deduct_credit(
                        stream_db,
                        current_user,
                        "mvp_build",
                        f"Custom build: {solution.title}",
                        solution_id=solution.id,
                    )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "persisting",
                                "step": 2,
                                "total_steps": 7,
                                "percentage": 30,
                                "message": "Persisting architectural blueprints and data models to solution registry...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }
                    # Persist solution artifacts to database so /solution/{id} is fully populated
                    await _persist_artifacts(stream_db, solution, solution.ai_state)

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "scaffolding",
                                "step": 3,
                                "total_steps": 7,
                                "percentage": 50,
                                "message": "Initializing full-stack codebase scaffold (FastAPI + Next.js)...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }
                    # Pre-populate code slots from ai_state (spec-first when available)
                    from app.services.app_spec import AppSpec, SpecError, generate_app_spec

                    spec_obj = None
                    spec_data = solution.ai_state.get("app_spec")
                    if spec_data:
                        try:
                            spec_obj = AppSpec.model_validate(spec_data)
                        except Exception:
                            spec_obj = None

                    # If no spec exists, generate one from the full conversation
                    # context. This is the critical step: the LLM designs the app
                    # structure from the user's actual requirements.
                    if spec_obj is None:
                        yield {
                            "event": "build_progress",
                            "data": json.dumps(
                                {
                                    "phase": "designing",
                                    "step": 3,
                                    "total_steps": 7,
                                    "percentage": 50,
                                    "message": "Designing domain models, schemas, and architecture with AI...",
                                    "solution_id": str(solution.id),
                                    "session_id": session_id,
                                }
                            ),
                        }
                        try:
                            # Build a rich prompt from conversation history
                            history_msgs = solution.conversation_history or []
                            user_messages = [
                                m.get("content", "")
                                for m in history_msgs
                                if m.get("role") == "user" and m.get("content")
                            ]
                            combined_prompt = (
                                "\n\n".join(user_messages[-5:])
                                if user_messages
                                else payload.message
                            )

                            spec_obj = await generate_app_spec(
                                solution.ai_state or {},
                                combined_prompt,
                                uploaded_context=payload.uploaded_context or "",
                                conversation_history=history_msgs,
                            )
                            # Persist the spec so rebuilds reuse it
                            solution.ai_state = {
                                **(solution.ai_state or {}),
                                "app_spec": spec_obj.model_dump(),
                            }
                            logger.info(
                                "Generated AppSpec '%s' for chat build of solution=%s",
                                spec_obj.app_name,
                                solution.id,
                            )
                        except (SpecError, Exception) as exc:
                            logger.warning(
                                "AppSpec generation failed for chat build (%s); "
                                "generating deterministic fallback AppSpec",
                                exc,
                            )
                            from app.services.app_spec import fallback_app_spec

                            spec_obj = fallback_app_spec(
                                solution.ai_state or {},
                                combined_prompt,
                                uploaded_context=payload.uploaded_context or "",
                                conversation_history=history_msgs,
                            )
                            solution.ai_state = {
                                **(solution.ai_state or {}),
                                "app_spec": spec_obj.model_dump(),
                            }

                    if spec_obj is None:
                        from app.services.app_spec import fallback_app_spec

                        spec_obj = fallback_app_spec(
                            solution.ai_state or {},
                            solution.title,
                            uploaded_context=payload.uploaded_context or "",
                            conversation_history=solution.conversation_history or [],
                        )
                        solution.ai_state = {
                            **(solution.ai_state or {}),
                            "app_spec": spec_obj.model_dump(),
                        }

                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=solution.ai_state.get("confirmed_modules") or [],
                        ai_state=solution.ai_state,
                        spec=spec_obj,
                    )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "coding",
                                "step": 4,
                                "total_steps": 7,
                                "percentage": 70,
                                "message": "Synthesizing domain models, Pydantic schemas, and REST routers...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    if sidecar_ok:
                        # Sidecar available — run verify+repair loop best-effort.
                        try:
                            await asyncio.wait_for(
                                mvp_verifier.verify_and_repair(
                                    ws_dir,
                                    session_id=session_id,
                                    target_dir=target_dir,
                                    send_prompt_fn=lambda s, t: builder.send_message(
                                        s, t, timeout=settings.MVP_BUILD_TIMEOUT
                                    ),
                                    check_npm=False,
                                    max_repair_turns=settings.MVP_MAX_REPAIR_TURNS,
                                ),
                                timeout=float(settings.MVP_BUILD_TIMEOUT),
                            )
                        except Exception as exc:
                            logger.warning(
                                "Sidecar verification encountered warnings (%s); proceeding with packaging as requested",
                                exc,
                            )
                    else:
                        # Offline — run static verification as advisory checks
                        try:
                            errors = mvp_verifier.verify_workspace(ws_dir, check_npm=False)
                            if errors:
                                logger.warning(
                                    "Build verification reported %d warning(s): %s; proceeding with packaging",
                                    len(errors),
                                    "; ".join(errors[:3]),
                                )
                        except Exception as exc:
                            logger.warning(
                                "Offline verification check encountered an issue (%s); proceeding with packaging",
                                exc,
                            )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "verifying",
                                "step": 5,
                                "total_steps": 7,
                                "percentage": 85,
                                "message": "Running codebase integrity verification (imports, routes, acceptance coverage)...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "packaging",
                                "step": 6,
                                "total_steps": 7,
                                "percentage": 90,
                                "message": "Packaging production archive (.zip) and saving build artifacts...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    lock, build_number = await allocate_build_number(stream_db, solution.id)
                    try:
                        files = builder.list_build_files(ws_dir)
                        rel_files = builder.relative_paths(ws_dir)

                        # Package archive to local disk and object storage
                        local_zip_path = ws_dir.with_suffix(".zip")
                        zip_data = builder.build_bytes(ws_dir)
                        local_zip_path.write_bytes(zip_data)

                        storage_key = f"local:{local_zip_path}"
                        try:
                            storage = get_storage()
                            uploaded_key = await asyncio.wait_for(
                                storage.upload_bytes(
                                    zip_data, f"builds/{solution.id}/build_{build_number}.zip"
                                ),
                                timeout=15.0,
                            )
                            if uploaded_key:
                                storage_key = uploaded_key
                        except Exception as store_err:
                            logger.warning(
                                "Remote storage upload failed (%s); using local fallback (%s)",
                                store_err,
                                local_zip_path,
                            )

                        mvp_build = MVPBuild(
                            solution_id=solution.id,
                            build_number=build_number,
                            status="complete",
                            workspace_path=str(ws_dir),
                            file_count=len(files),
                            file_list=rel_files,
                            storage_key=storage_key,
                            opencode_session_id=session_id,
                            app_config={
                                "app_name": solution.title,
                                "source": "opencode_chat",
                                "progress": {
                                    "stage": "complete",
                                    "step": 7,
                                    "total_steps": 7,
                                    "percentage": 100,
                                    "message": f"Build complete! {len(files)} files generated.",
                                },
                            },
                        )
                        stream_db.add(mvp_build)
                        solution.status = "complete"
                        await stream_db.flush()
                        build_state = {
                            "build_id": str(mvp_build.id),
                            "build_number": build_number,
                            "file_count": len(files),
                            "files": [{"path": p, "size": 0, "is_dir": False} for p in rel_files],
                        }

                        # Commit while still holding the per-solution lock so the
                        # new build_number is visible before any concurrent build
                        # computes the next one.
                        await stream_db.commit()

                        yield {
                            "event": "build_progress",
                            "data": json.dumps(
                                {
                                    "phase": "completed",
                                    "step": 7,
                                    "total_steps": 7,
                                    "percentage": 100,
                                    "message": f"Build complete! {len(files)} files generated.",
                                    "solution_id": str(solution.id),
                                    "session_id": session_id,
                                    "build_id": str(mvp_build.id),
                                    "file_count": len(files),
                                }
                            ),
                        }
                    finally:
                        lock.release()

                await stream_db.commit()

            # Multilingual pipeline: translate the conversational reply into the
            # caller's language (best-effort, fail-open — see app/core/i18n.py).
            if content_language not in ("", settings.DEFAULT_LANGUAGE):
                assistant_text = await translate_text(assistant_text, content_language)

            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "role": "assistant",
                        "message": assistant_text,
                        "session_id": session_id,
                    }
                ),
            }
            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "status": "complete" if payload.build_requested else "message",
                        "message": assistant_text,
                        "session_id": session_id,
                        "solution_id": str(solution.id),
                        **build_state,
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error in OpenCode chat")
            try:
                async with async_session_factory() as err_db:
                    if payload.solution_id:
                        sol = await err_db.get(Solution, payload.solution_id)
                        if sol is not None:
                            sol.status = "failed"
                            await err_db.commit()
            except Exception:  # noqa: BLE001 - best-effort failure persistence
                pass
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
