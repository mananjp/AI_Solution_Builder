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

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.chat import _persist_artifacts
from app.core.config import settings
from app.core.credits import require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.llm import get_llm
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


def _synthesize_domain_artifacts(title: str, user_prompt: str) -> dict[str, Any]:
    text = f"{title} {user_prompt}".lower()
    industry: str
    modules: list[str]
    entities: list[dict[str, Any]]

    if any(
        k in text
        for k in ("retail", "store", "ecommerce", "inventory", "pos", "shop", "product", "stock")
    ):
        industry = "d2c_retail"
        modules = ["ecommerce_storefront", "inventory_management", "order_fulfillment", "crm"]
        entities = [
            {
                "name": "products",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "sku", "type": "VARCHAR(100)"},
                    {"name": "price", "type": "FLOAT"},
                ],
            },
            {
                "name": "orders",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "customer_name", "type": "VARCHAR(255)"},
                    {"name": "total", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "customers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                ],
            },
            {
                "name": "inventory",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "product_name", "type": "VARCHAR(255)"},
                    {"name": "quantity", "type": "INTEGER"},
                ],
            },
        ]
    elif any(
        k in text for k in ("health", "clinic", "doctor", "patient", "medical", "telehealth", "ehr")
    ):
        industry = "healthcare_clinic"
        modules = ["booking_scheduler", "patient_portal", "prescriptions", "invoicing_billing"]
        entities = [
            {
                "name": "patients",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "dob", "type": "VARCHAR(50)"},
                    {"name": "phone", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "doctors",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "specialty", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "appointments",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "patient_name", "type": "VARCHAR(255)"},
                    {"name": "appointment_date", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "prescriptions",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "patient_name", "type": "VARCHAR(255)"},
                    {"name": "medication", "type": "VARCHAR(255)"},
                ],
            },
        ]
    elif any(
        k in text
        for k in ("logistics", "fleet", "dispatch", "driver", "freight", "truck", "shipment")
    ):
        industry = "logistics_company"
        modules = [
            "order_fulfillment",
            "fleet_tracking",
            "dispatch_management",
            "invoicing_billing",
        ]
        entities = [
            {
                "name": "shipments",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "tracking_number", "type": "VARCHAR(100)"},
                    {"name": "destination", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "drivers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "license_number", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "vehicles",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "plate_number", "type": "VARCHAR(50)"},
                    {"name": "model", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "routes",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "origin", "type": "VARCHAR(255)"},
                    {"name": "destination", "type": "VARCHAR(255)"},
                ],
            },
        ]
    elif any(k in text for k in ("crm", "lead", "client", "sales", "deal")):
        industry = "consulting_agency"
        modules = ["crm", "deal_pipeline", "client_portal", "invoicing_billing"]
        entities = [
            {
                "name": "leads",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "company", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "clients",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "industry", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "deals",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "amount", "type": "FLOAT"},
                    {"name": "stage", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "activities",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "activity_type", "type": "VARCHAR(50)"},
                    {"name": "notes", "type": "VARCHAR(500)"},
                ],
            },
        ]
    else:
        industry = "saas_platform"
        modules = ["core_crud", "user_management", "analytics_dashboard", "invoicing_billing"]
        entities = [
            {
                "name": "items",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "categories",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "VARCHAR(255)"},
                ],
            },
            {
                "name": "users",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                ],
            },
        ]

    # Build DDL
    ddl_statements: list[str] = []
    for ent in entities:
        ent_name = str(ent["name"])
        ent_fields = cast(list[dict[str, str]], ent.get("fields", []))
        cols = ", ".join(f"{f['name']} {f['type']}" for f in ent_fields)
        ddl_statements.append(f"CREATE TABLE {ent_name} ({cols});")
    schema_ddl = "\n".join(ddl_statements)

    # Build Endpoints
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
                "name": f"{ent_name.capitalize()} Dashboard",
                "route": f"/{ent_name}",
                "description": f"CRUD management for {ent_name}",
                "layout": "sidebar",
                "components": [
                    {
                        "type": "data_table",
                        "title": f"{ent_name.capitalize()} Table",
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


@router.get("/health")
async def health() -> dict[str, Any]:
    """Report whether the AI build engine is reachable and ready.

    ``healthy`` is ``True`` whenever the service can handle a request —
    either via the live sidecar *or* via the integrated synthesizer
    fallback.  ``sidecar_healthy`` reports the sidecar process itself.
    """
    sidecar_ok = await builder.health()
    return {
        "healthy": True,
        "sidecar_healthy": sidecar_ok,
        "mode": "opencode-sidecar" if sidecar_ok else "integrated-synthesizer",
    }


async def _verify_solution_access(db: AsyncSession, solution_id: UUID, user: User) -> Solution:
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == user.org_id)
    )
    solution = result.scalar_one_or_none()
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


async def _next_build_number(db: AsyncSession, solution_id: UUID) -> int:
    result = await db.execute(
        select(MVPBuild.build_number)
        .where(MVPBuild.solution_id == solution_id)
        .order_by(desc(MVPBuild.build_number))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1


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
    # Eager ownership check so authorization failures surface as HTTP errors
    # rather than mid-stream error events.
    if payload.solution_id:
        await _verify_solution_access(db, payload.solution_id, current_user)

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            # Streaming over a dependency-injected session is unsafe (see
            # chat.py for the rationale) — open an explicit session here.
            async with async_session_factory() as stream_db:
                if payload.solution_id:
                    solution = await _verify_solution_access(
                        stream_db, payload.solution_id, current_user
                    )
                else:
                    workspace = await _get_or_create_workspace(stream_db, current_user)
                    solution = Solution(
                        workspace_id=workspace.id,
                        title=payload.app_name or "Custom App Build",
                        description="App built through conversational OpenCode chat",
                        status="discovery",
                        conversation_history=[],
                    )
                    stream_db.add(solution)
                    await stream_db.flush()

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

                    response = await builder.send_message(
                        session_id,
                        instruction,
                        agent=settings.OPENCODE_AGENT,
                    )

                    assistant_text = _extract_text(response) or (
                        "Done — tell me what to change next, or hit Build & Deploy "
                        "to finalize the app."
                    )
                else:
                    # Integrated synthesizer — direct LLM conversation.
                    llm = get_llm()
                    sys_prompt = (
                        "You are an expert full-stack AI Developer for AI Solution Builder. "
                        "You are helping the user architect and build a complete "
                        "FastAPI + Next.js application. A full working scaffold with "
                        "database, auth, and API structure is already configured. "
                        "Respond informatively to their requirements, explain which "
                        "models, API routes, and pages are being generated, and "
                        "confirm that the workspace is ready to finalize. "
                        "Keep your response concise, structured, and practical."
                    )
                    user_prompt = payload.message
                    if payload.uploaded_context:
                        user_prompt = (
                            f"Context from uploaded document:\n"
                            f"{payload.uploaded_context[:_TARGET_MAX_CONTEXT]}\n\n"
                            f"User request:\n{user_prompt}"
                        )

                    resp = await llm.ainvoke(
                        [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
                    )
                    assistant_text = ""
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
                    if not assistant_text:
                        assistant_text = (
                            "I've structured your application requirements into the "
                            "FastAPI backend and Next.js frontend workspace. "
                            "Toggle **Build** and send to finalize your deployable package."
                        )

                history = solution.conversation_history or []
                history.append({"role": "user", "content": payload.message})
                history.append({"role": "assistant", "content": assistant_text})
                solution.conversation_history = history

                synthesized = _synthesize_domain_artifacts(solution.title, payload.message)
                solution.ai_state = {
                    **synthesized,
                    **ai_state,
                    "business_description": ai_state.get("business_description") or payload.message,
                }

                build_state: dict[str, Any] = {}
                if payload.build_requested:
                    await require_and_deduct_credit(
                        stream_db,
                        current_user,
                        "mvp_build",
                        f"Custom build: {solution.title}",
                        solution_id=solution.id,
                    )
                    # Persist solution artifacts to database so /solution/{id} is fully populated
                    await _persist_artifacts(stream_db, solution, solution.ai_state)

                    # Pre-populate code slots from ai_state
                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=solution.ai_state.get("confirmed_modules") or [],
                        ai_state=solution.ai_state,
                    )

                    if sidecar_ok:
                        # Sidecar available — run full verify+repair loop.
                        try:
                            await mvp_verifier.verify_and_repair(
                                ws_dir,
                                session_id=session_id,
                                target_dir=target_dir,
                                send_prompt_fn=lambda s, t: builder.send_message(s, t),
                                check_npm=False,
                                max_repair_turns=2,
                            )
                        except mvp_verifier.VerificationError as exc:
                            raise RuntimeError(f"Build verification failed: {exc}") from exc
                    else:
                        # Offline — run read-only verification, fail honestly
                        # if the synthesized scaffold is broken.
                        errors = mvp_verifier.verify_workspace(ws_dir, check_npm=False)
                        if errors:
                            error_summary = "; ".join(errors[:5])
                            raise RuntimeError(
                                f"Build verification failed ({len(errors)} error(s)): "
                                f"{error_summary}"
                            )

                    build_number = await _next_build_number(stream_db, solution.id)
                    files = builder.list_build_files(ws_dir)
                    rel_files = builder.relative_paths(ws_dir)

                    # Package archive to local disk and object storage
                    local_zip_path = ws_dir.with_suffix(".zip")
                    zip_data = builder.build_bytes(ws_dir)
                    local_zip_path.write_bytes(zip_data)

                    storage_key = f"local:{local_zip_path}"
                    try:
                        storage = get_storage()
                        uploaded_key = await storage.upload_bytes(
                            zip_data, f"builds/{solution.id}/build_{build_number}.zip"
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

                await stream_db.commit()

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
