"""
AI Solution Builder — Artifact Regeneration & Versioning API
(Section 6 of the implementation plan)

Allows isolated re-running of a single agent node against prior state + user feedback,
saving a new version in `solution_artifacts` without discarding other artifacts.
"""

import logging
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.blueprint_generator import blueprint_generator_node
from app.agents.nodes.database_api_agent import database_api_agent_node
from app.agents.nodes.process_intelligence import process_intelligence_node
from app.agents.nodes.solutions_architect import solutions_architect_node
from app.agents.nodes.ux_agent import ux_agent_node
from app.agents.state import DiscoveryState
from app.core.credits import refund_credit, require_and_deduct_credit
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.artifact import ArtifactComment, SolutionArtifact
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.services.artifact_graph import normalize_artifact_type
from app.services.image_gen import is_image_artifact
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["Artifacts & Regeneration"])


class RegenerateRequest(BaseModel):
    solution_id: UUID
    artifact_type: str  # 'hld', 'lld', 'wireframe', 'database_schema', 'api_spec', 'roadmap', 'bpmn_flows' (legacy 'bpmn' accepted)
    user_feedback: str


class ArtifactVersionResponse(BaseModel):
    id: UUID
    solution_id: UUID
    artifact_type: str
    title: str
    version: int
    content: dict[str, Any]
    content_text: str | None
    created_at: str


class CommentCreate(BaseModel):
    body: str


class CommentResponse(BaseModel):
    id: UUID
    artifact_id: UUID
    author_id: UUID
    body: str
    resolved: bool
    created_at: str


async def _verify_artifact_access(
    artifact_id: UUID, current_user: User, db: AsyncSession
) -> tuple[SolutionArtifact, Solution]:
    """Ensure the user can access a solution containing the artifact."""
    result = await db.execute(
        select(SolutionArtifact, Solution)
        .join(Solution, Solution.id == SolutionArtifact.solution_id)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            SolutionArtifact.id == artifact_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return row[0], row[1]


def _comment_payload(comment: ArtifactComment) -> dict[str, Any]:
    return {
        "id": comment.id,
        "artifact_id": comment.artifact_id,
        "author_id": comment.author_id,
        "body": comment.body,
        "resolved": comment.resolved,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.post("/{artifact_id}/comments", status_code=201)
async def add_comment(
    artifact_id: UUID,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Attach a collaboration comment to a specific artifact version."""
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")

    artifact, _solution = await _verify_artifact_access(artifact_id, current_user, db)
    comment = ArtifactComment(
        artifact_id=artifact.id,
        author_id=current_user.id,
        body=payload.body.strip(),
        resolved=False,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return _comment_payload(comment)


@router.get("/{artifact_id}/comments")
async def list_comments(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List collaboration comments for an artifact version (newest first)."""
    await _verify_artifact_access(artifact_id, current_user, db)
    result = await db.execute(
        select(ArtifactComment)
        .where(ArtifactComment.artifact_id == artifact_id)
        .order_by(desc(ArtifactComment.created_at))
    )
    return [_comment_payload(c) for c in result.scalars().all()]


@router.patch("/comments/{comment_id}/resolve")
async def resolve_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mark a comment as resolved (approval-style activity tracking)."""
    result = await db.execute(
        select(ArtifactComment)
        .join(SolutionArtifact, SolutionArtifact.id == ArtifactComment.artifact_id)
        .join(Solution, Solution.id == SolutionArtifact.solution_id)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            ArtifactComment.id == comment_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.resolved = True
    await db.commit()
    await db.refresh(comment)
    return _comment_payload(comment)


@router.get("/activity/{solution_id}")
async def solution_activity(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Activity log for a solution (collaboration comments across all versions)."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == current_user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Solution not found")

    events = await db.execute(
        select(ArtifactComment, SolutionArtifact.artifact_type)
        .join(SolutionArtifact, SolutionArtifact.id == ArtifactComment.artifact_id)
        .where(SolutionArtifact.solution_id == solution_id)
        .order_by(desc(ArtifactComment.created_at))
    )
    return {
        "solution_id": solution_id,
        "events": [
            {
                **_comment_payload(comment),
                "artifact_type": artifact_type,
            }
            for comment, artifact_type in events.all()
        ],
    }


@router.get("/{solution_id}/history/{artifact_type}")
async def get_artifact_history(
    solution_id: UUID,
    artifact_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get version history for a specific artifact type in a solution."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == current_user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Solution not found")

    artifacts_res = await db.execute(
        select(SolutionArtifact)
        .where(
            SolutionArtifact.solution_id == solution_id,
            SolutionArtifact.artifact_type == artifact_type,
        )
        .order_by(desc(SolutionArtifact.version))
    )
    artifacts = artifacts_res.scalars().all()
    return [
        {
            "id": a.id,
            "solution_id": a.solution_id,
            "artifact_type": a.artifact_type,
            "title": a.title,
            "version": a.version,
            "content": a.content,
            "content_text": a.content_text,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in artifacts
    ]


@router.post("/regenerate")
async def regenerate_artifact(
    payload: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Scoped Regeneration: Re-runs only the relevant agent node with user feedback,
    creating a new version in `solution_artifacts`.
    """
    # Normalize legacy UI names (e.g. 'bpmn') to the canonical stored artifact type.
    payload.artifact_type = normalize_artifact_type(payload.artifact_type)

    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == payload.solution_id, Workspace.org_id == current_user.org_id)
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    # Fetch latest version of this artifact
    latest_art_res = await db.execute(
        select(SolutionArtifact)
        .where(
            SolutionArtifact.solution_id == payload.solution_id,
            SolutionArtifact.artifact_type == payload.artifact_type,
        )
        .order_by(desc(SolutionArtifact.version))
        .limit(1)
    )
    latest_artifact = latest_art_res.scalar_one_or_none()
    next_version = (latest_artifact.version + 1) if latest_artifact else 1

    # Base state from solution
    ai_state = solution.ai_state or {}
    prior_state = {
        **ai_state,
        "user_message": f"Regeneration request for {payload.artifact_type}: {payload.user_feedback}",
        "user_feedback": payload.user_feedback,
    }

    new_content = {}
    new_text = ""
    new_title = f"{payload.artifact_type.upper()} (v{next_version})"

    # Generated visuals are produced by the illustration phase, not by a
    # regenerable agent node. Without this guard the dispatch chain below would
    # fall through to its generic `else` branch and write a placeholder row with
    # no storage_key, so the newest version could never load an image. Reject
    # before the credit is deducted: the refund path only covers exceptions.
    if is_image_artifact(payload.artifact_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{payload.artifact_type}' artifacts are generated during the build "
                "and cannot be regenerated. Re-run the build to produce new visuals."
            ),
        )

    # Meter the regeneration through the shared credit gate (402 if insufficient)
    await require_and_deduct_credit(
        db,
        current_user,
        "regenerate",
        f"Regenerated {payload.artifact_type} v{next_version}",
        solution_id=payload.solution_id,
    )

    try:
        # Route to appropriate agent node based on artifact_type
        if payload.artifact_type in ("hld", "lld"):
            output = await solutions_architect_node(cast(DiscoveryState, prior_state))
            art = output.get(payload.artifact_type, {})
            new_content = art.get("content", {})
            new_text = art.get(
                "content_text",
                f"Regenerated {payload.artifact_type.upper()} based on feedback: {payload.user_feedback}",
            )
            new_title = art.get("title", f"{payload.artifact_type.upper()} Blueprint")
        elif payload.artifact_type == "wireframe":
            output = await ux_agent_node(cast(DiscoveryState, prior_state))
            wfs = output.get("wireframes", [])
            new_content = wfs[0].get("content", {}) if wfs else {}
            new_text = (
                wfs[0].get("content_text", "")
                if wfs
                else f"Wireframe regenerated with: {payload.user_feedback}"
            )
            new_title = wfs[0].get("title", "UI Wireframe") if wfs else "Wireframe Blueprint"
        elif payload.artifact_type in ("database_schema", "er_diagram", "api_spec"):
            output = await database_api_agent_node(cast(DiscoveryState, prior_state))
            art = output.get(payload.artifact_type, {})
            new_content = art.get("content", {})
            new_text = art.get(
                "content_text", f"Regenerated {payload.artifact_type} with: {payload.user_feedback}"
            )
            new_title = art.get("title", payload.artifact_type.replace("_", " ").title())
        elif payload.artifact_type == "roadmap":
            output = await blueprint_generator_node(cast(DiscoveryState, prior_state))
            art = output.get("roadmap", {})
            new_content = art.get("content", {})
            new_text = art.get(
                "content_text", f"Regenerated roadmap based on: {payload.user_feedback}"
            )
            new_title = art.get("title", "Delivery Roadmap & Milestones")
        elif payload.artifact_type == "bpmn_flows":
            output = await process_intelligence_node(cast(DiscoveryState, prior_state))
            flows = output.get("bpmn_flows", [])
            if flows:
                flow = flows[0]
                new_content = flow.get("content", {})
                new_text = flow.get(
                    "content_text", f"Regenerated BPMN workflows with: {payload.user_feedback}"
                )
                new_title = flow.get("title", "Process Workflows")
            else:
                new_text = f"Regenerated BPMN workflows with: {payload.user_feedback}"
                new_content = {"flows": [], "react_flow": {"nodes": [], "edges": []}}
        else:
            new_text = f"Regenerated {payload.artifact_type}: {payload.user_feedback}"
            new_content = {"custom_spec": payload.user_feedback}
    except Exception as err:
        logger.error(
            f"Agent execution failed during regeneration of {payload.artifact_type}: {err}",
            exc_info=True,
        )
        await refund_credit(
            db,
            current_user,
            "regenerate",
            description=f"Refund for failed {payload.artifact_type} regeneration",
            solution_id=payload.solution_id,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Regeneration agent failed for {payload.artifact_type}: {err}",
        ) from err

    # Save new artifact version
    new_artifact = SolutionArtifact(
        solution_id=payload.solution_id,
        artifact_type=payload.artifact_type,
        title=new_title,
        content=new_content,
        content_text=new_text,
        version=next_version,
    )
    db.add(new_artifact)
    await db.commit()
    await db.refresh(new_artifact)

    return {
        "status": "success",
        "message": f"Successfully regenerated {payload.artifact_type} to version {next_version}",
        "artifact": {
            "id": new_artifact.id,
            "solution_id": new_artifact.solution_id,
            "artifact_type": new_artifact.artifact_type,
            "title": new_artifact.title,
            "version": new_artifact.version,
            "content": new_artifact.content,
            "content_text": new_artifact.content_text,
            "created_at": new_artifact.created_at.isoformat() if new_artifact.created_at else None,
        },
    }


@router.get("/{artifact_id}/image")
async def get_artifact_image(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the bytes of a generated product visual.

    Images are served through the API rather than from public object-storage
    URLs so that access control is identical to every other artifact, and so the
    same code path works for the local disk backend and Cloudinary (which stores
    everything as ``resource_type="raw"`` and therefore has no directly
    renderable URL).
    """
    artifact, _solution = await _verify_artifact_access(artifact_id, current_user, db)

    if not is_image_artifact(artifact.artifact_type):
        raise HTTPException(status_code=404, detail="Artifact does not contain a generated image")

    content = artifact.content or {}
    image_meta = content.get("image")
    if not isinstance(image_meta, dict):
        raise HTTPException(status_code=404, detail="Artifact has no image payload")
    storage_key = image_meta.get("storage_key")
    if not storage_key:
        raise HTTPException(status_code=404, detail="Artifact has no image storage key")

    mime_type = str(image_meta.get("mime_type") or "image/png")
    if not mime_type.startswith("image/"):
        # Never echo an attacker-controlled content type back as a response
        # header; fall back to a safe default instead.
        mime_type = "image/png"

    try:
        data = await get_storage().download_raw(str(storage_key))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Image bytes no longer available") from exc
    except Exception as exc:  # noqa: BLE001 - upstream storage failure
        logger.error("Failed to read image artifact %s: %s", artifact_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Image storage unavailable"
        ) from exc

    return Response(
        content=data,
        media_type=mime_type,
        headers={
            # Artifact bytes are immutable per version, so they cache hard.
            "Cache-Control": "private, max-age=86400, immutable",
            "Content-Disposition": f'inline; filename="{artifact.artifact_type}.png"',
        },
    )


@router.get("/{artifact_id}/explain")
async def explain_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve explainability details (decisions, assumptions, evidence, confidence) for an artifact."""
    result = await db.execute(
        select(SolutionArtifact)
        .join(Solution, Solution.id == SolutionArtifact.solution_id)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            SolutionArtifact.id == artifact_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    content = artifact.content or {}
    decisions = content.get("decisions", [])

    assumptions: list[str] = []
    evidence: list[dict[str, Any]] = []
    confidences: list[float] = []

    for dec in decisions:
        assumptions.extend(dec.get("assumptions", []))
        evidence.extend(dec.get("evidence", []))
        if "confidence" in dec:
            confidences.append(float(dec["confidence"]))

    if "evidence" in content and isinstance(content["evidence"], list):
        evidence.extend(content["evidence"])
    if "assumptions" in content and isinstance(content["assumptions"], list):
        assumptions.extend(content["assumptions"])

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.90

    return {
        "artifact_id": str(artifact.id),
        "solution_id": str(artifact.solution_id),
        "artifact_type": artifact.artifact_type,
        "title": artifact.title,
        "version": artifact.version,
        "decisions": decisions,
        "assumptions": list(dict.fromkeys(assumptions)),
        "evidence": evidence,
        "confidence": round(avg_confidence, 2),
    }
