"""
AI Solution Builder — Chat API Route

Streaming SSE endpoint for the AI chat assistant.
Runs the LangGraph pipeline, streams agent progress events, persists all
generated artifacts (including BPMN flows and the workable schema), and
deducts credits via the credit metering service.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import discovery_graph, generation_graph
from app.agents.state import DiscoveryState
from app.core.credits import require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.i18n import translate_text
from app.core.security import get_current_user
from app.models.artifact import SolutionArtifact
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import ChatMessage, RecommendationConfirm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

ARTIFACT_TYPES = ["hld", "lld", "er_diagram", "database_schema", "api_spec", "roadmap"]


async def _verify_solution_access(solution_id: UUID, user: User, db: AsyncSession) -> Solution:
    """Verify the user has access to the solution and return it."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


async def _persist_artifacts(
    db: AsyncSession, solution: Solution, final_state: dict[str, Any]
) -> None:
    """Save all generated artifacts (scalar, wireframe, and BPMN lists) as new rows."""
    max_version: dict[str, int] = {}
    rows = (
        await db.execute(
            select(SolutionArtifact.artifact_type, SolutionArtifact.version).where(
                SolutionArtifact.solution_id == solution.id
            )
        )
    ).all()
    for artifact_type, version in rows:
        max_version[artifact_type] = max(max_version.get(artifact_type, 0), version)

    def add(artifact_type: str, title: str, content: dict[str, Any], content_text: str) -> None:
        next_version = max_version.get(artifact_type, 0) + 1
        max_version[artifact_type] = next_version
        db.add(
            SolutionArtifact(
                solution_id=solution.id,
                artifact_type=artifact_type,
                title=title,
                content=content or {},
                content_text=content_text or "",
                version=next_version,
            )
        )

    for artifact_type in ARTIFACT_TYPES:
        artifact_data = final_state.get(artifact_type)
        if artifact_data and isinstance(artifact_data, dict) and "content" in artifact_data:
            add(
                artifact_data.get("artifact_type", artifact_type),
                artifact_data.get("title", artifact_type),
                artifact_data.get("content", {}),
                artifact_data.get("content_text", ""),
            )

    for wf in final_state.get("wireframes", []):
        if isinstance(wf, dict) and "content" in wf:
            add(
                "wireframe",
                wf.get("title", "Wireframe"),
                wf.get("content", {}),
                wf.get("content_text", ""),
            )

    for flow in final_state.get("bpmn_flows", []):
        if isinstance(flow, dict) and "content" in flow:
            add(
                flow.get("artifact_type", "bpmn_flows"),
                flow.get("title", "Process Workflow"),
                flow.get("content", {}),
                flow.get("content_text", ""),
            )

    generated = final_state.get("generated_schema")
    if generated and isinstance(generated, dict) and "content" in generated:
        add(
            "workable_schema",
            generated.get("title", "Executable Database Schema"),
            generated.get("content", {}),
            generated.get("content_text", ""),
        )


async def _stream_final_state(
    db: AsyncSession, solution: Solution, final_state: dict[str, Any], end_status: str
) -> dict[str, Any]:
    """Save artifacts + update solution state; return the completion payload."""
    await _persist_artifacts(db, solution, final_state)

    solution.ai_state = {
        k: v for k, v in final_state.items() if k not in ("agent_messages",) and not callable(v)
    }
    solution.status = end_status

    if end_status == "complete":
        return {
            "status": "complete",
            "message": "Your complete solution has been generated — including architecture, wireframes, process workflows, database schema, API specs, and the implementation roadmap. Check the artifacts tab, and the Workable tab to open the live running system.",
        }
    return {"status": end_status, "message": ""}


async def _generation_response(
    solution: Solution,
    final_state: dict[str, Any],
    ai_response: str,
    conversation_history: list[dict[str, Any]],
) -> dict[str, Any]:
    conversation_history.append({"role": "assistant", "content": ai_response})
    solution.conversation_history = conversation_history
    return final_state


@router.post("/send")
async def send_message(
    payload: ChatMessage,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Send a message to the AI pipeline and get a streaming response."""
    # Eager access check so authorization failures surface as HTTP errors
    # rather than error events mid-stream.
    await _verify_solution_access(payload.solution_id, current_user, db)
    content_language: str = getattr(request.state, "language", "en")

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            yield {
                "event": "agent_start",
                "data": json.dumps({"agent": "pipeline", "message": "Starting AI analysis..."}),
            }

            # Streaming over a dependency-injected session is unsafe: the yield
            # teardown closes the request session before the response body is
            # consumed, orphaning ORM objects. Open an explicit session here so
            # artifact/status persistence outlives the endpoint return.
            async with async_session_factory() as stream_db:
                solution = await _verify_solution_access(
                    payload.solution_id, current_user, stream_db
                )

                await require_and_deduct_credit(
                    stream_db, current_user, "generation", f"Chat analysis: {solution.title}"
                )

                conversation_history = solution.conversation_history or []
                conversation_history.append({"role": "user", "content": payload.message})

                ai_state = solution.ai_state or {}
                initial_state = {
                    "user_message": payload.message,
                    "uploaded_context": payload.uploaded_context
                    or ai_state.get("uploaded_context", ""),
                    "conversation_history": conversation_history,
                    "agent_messages": [],
                    **{
                        k: v
                        for k, v in ai_state.items()
                        if k not in ("user_message", "conversation_history", "agent_messages")
                    },
                }

                final_state = await discovery_graph.ainvoke(cast(DiscoveryState, initial_state))

                for msg in final_state.get("agent_messages", []):
                    yield {"event": msg.get("type", "agent_progress"), "data": json.dumps(msg)}

                status = final_state.get("status", "complete")

                if status == "recommending":
                    ai_response = f"Based on my analysis, I've identified your business as a {final_state.get('industry', 'general')} operation. I have some module recommendations for you — please review and confirm which ones you'd like to build."
                elif status == "complete":
                    completion = await _stream_final_state(
                        stream_db, solution, final_state, "complete"
                    )
                    ai_response = completion["message"]
                else:
                    questions = final_state.get("clarification_questions", [])
                    ai_response = (
                        "I need a bit more information to proceed:\n"
                        + "\n".join(f"- {q}" for q in questions)
                        if questions
                        else "I've analyzed your requirements. Let me know if you'd like to proceed or provide more details."
                    )

                ai_response = await translate_text(ai_response, content_language)

                await _generation_response(solution, final_state, ai_response, conversation_history)
                await stream_db.commit()

            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "status": status,
                        "message": ai_response,
                        "recommendations": final_state.get("recommended_modules")
                        if status == "recommending"
                        else None,
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error in chat pipeline")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())


@router.post("/confirm-recommendations")
async def confirm_recommendations(
    payload: RecommendationConfirm,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Confirm recommended modules and trigger the generation pipeline."""
    # Eager access check so authorization failures surface as HTTP errors
    # rather than error events mid-stream.
    await _verify_solution_access(payload.solution_id, current_user, db)
    content_language: str = getattr(request.state, "language", "en")

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            yield {
                "event": "agent_start",
                "data": json.dumps({"agent": "pipeline", "message": "Generating your solution..."}),
            }

            # Own session: see send_message for rationale (yield teardown would
            # close a dependency-injected session before streaming completes).
            async with async_session_factory() as stream_db:
                solution = await _verify_solution_access(
                    payload.solution_id, current_user, stream_db
                )
                await require_and_deduct_credit(
                    stream_db, current_user, "generation", f"Full generation: {solution.title}"
                )

                ai_state = solution.ai_state or {}
                conversation_history = solution.conversation_history or []

                initial_state = {
                    **ai_state,
                    "confirmed_modules": payload.accepted_modules,
                    "identified_solutions": payload.accepted_modules,
                    "conversation_history": conversation_history,
                    "agent_messages": [],
                }

                conversation_history.append(
                    {
                        "role": "user",
                        "content": f"I'd like to build these modules: {', '.join(payload.accepted_modules)}",
                    }
                )

                final_state = await generation_graph.ainvoke(cast(DiscoveryState, initial_state))

                for msg in final_state.get("agent_messages", []):
                    yield {"event": msg.get("type", "agent_progress"), "data": json.dumps(msg)}

                completion = await _stream_final_state(stream_db, solution, final_state, "complete")
                ai_response = completion["message"]
                ai_response = await translate_text(ai_response, content_language)
                await _generation_response(solution, final_state, ai_response, conversation_history)

                # Log the recommendation event for template-library feedback (Section 4)
                try:
                    from app.models.recommendation import RecommendationEvent

                    stream_db.add(
                        RecommendationEvent(
                            workspace_id=solution.workspace_id,
                            industry_classified=final_state.get("industry"),
                            modules_proposed=[
                                m.get("module") for m in final_state.get("recommended_modules", [])
                            ],
                            modules_accepted=payload.accepted_modules,
                        )
                    )
                except Exception:
                    logger.warning("Failed to record recommendation event")

                await stream_db.commit()

            yield {
                "event": "complete",
                "data": json.dumps({"status": "complete", "message": ai_response}),
            }

        except Exception as e:
            logger.exception("Error in generation pipeline")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
