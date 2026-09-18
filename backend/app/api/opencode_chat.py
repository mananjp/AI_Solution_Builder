"""
AI Solution Builder — OpenCode Direct Chat API

Lets the user chat directly with the OpenCode sidecar (the "Custom App
Builder" path). Each solution keeps a persistent OpenCode session and a
scaffolded workspace; the agent edits files in-place as the conversation
progresses. When the user asks to finish (``build_requested``), the workspace
is verified/repaired and finalized into an ``MVPBuild`` for download/deploy.

Endpoints:
    GET  /api/v1/opencode/health      Sidecar liveness probe (dashboard banner)
    POST /api/v1/opencode/chat        SSE chat stream (build_requested finalizes)
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opencode", tags=["OpenCode Chat"])

_TARGET_MAX_CONTEXT = 20_000  # uploaded-context cap fed to the sidecar


@router.get("/health")
async def health() -> dict[str, Any]:
    """Report whether the AI build engine is reachable and ready."""
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
                        ai_state=ai_state,
                    )

                target_dir = builder.chat_container_target(solution.id)

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
                        "Done — tell me what to change next, or hit Build & Deploy to finalize the app."
                    )
                else:
                    llm = get_llm()
                    sys_prompt = (
                        "You are an expert full-stack AI Developer for AI Solution Builder. "
                        "You are helping the user architect and build a complete FastAPI + Next.js application. "
                        "A full working scaffold with database, auth, and API structure is already configured. "
                        "Respond informatively to their requirements, explain which models, API routes, "
                        "and pages are being generated, and confirm that the workspace is ready to finalize. "
                        "Keep your response concise, structured, and practical."
                    )
                    user_prompt = payload.message
                    if payload.uploaded_context:
                        user_prompt = f"Context from uploaded document:\n{payload.uploaded_context[:_TARGET_MAX_CONTEXT]}\n\nUser request:\n{user_prompt}"

                    resp = await llm.ainvoke(
                        [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
                    )
                    assistant_text = (
                        str(resp.content)
                        if resp and resp.content
                        else "I've structured your application requirements into the FastAPI backend and Next.js frontend workspace. Click **Build App** to finalize."
                    )

                history = solution.conversation_history or []
                history.append({"role": "user", "content": payload.message})
                history.append({"role": "assistant", "content": assistant_text})
                solution.conversation_history = history
                solution.ai_state = {
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
                    # Pre-populate code slots from ai_state
                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=[],
                        ai_state=solution.ai_state,
                    )
                    try:
                        await mvp_verifier.verify_and_repair(
                            ws_dir,
                            session_id=session_id if sidecar_ok else None,
                            target_dir=target_dir,
                            send_prompt_fn=(lambda s, t: builder.send_message(s, t))
                            if sidecar_ok
                            else None,
                            check_npm=False,
                            max_repair_turns=2 if sidecar_ok else 0,
                        )
                    except mvp_verifier.VerificationError as exc:
                        if sidecar_ok:
                            raise RuntimeError(f"Build verification failed: {exc}") from exc
                        logger.warning("Integrated build verification warning: %s", exc)

                    build_number = await _next_build_number(stream_db, solution.id)
                    mvp_build = MVPBuild(
                        solution_id=solution.id,
                        build_number=build_number,
                        status="complete",
                        workspace_path=str(ws_dir),
                        file_count=len(builder.list_build_files(ws_dir)),
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
