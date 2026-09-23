"""
AI Solution Builder — Solution API Routes

CRUD for solutions + artifact retrieval.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import (
    ArtifactResponse,
    SolutionCreate,
    SolutionDetailResponse,
    SolutionResponse,
)

router = APIRouter(prefix="/solutions", tags=["Solutions"])


@router.post("/", response_model=SolutionResponse, status_code=status.HTTP_201_CREATED)
async def create_solution(
    payload: SolutionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Solution:
    """Create a new solution (starts the AI discovery process)."""
    # Verify workspace belongs to user's org
    ws_result = await db.execute(
        select(Workspace).where(
            Workspace.id == payload.workspace_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    solution = Solution(
        workspace_id=payload.workspace_id,
        title=payload.title,
        description=payload.description,
        status="discovery",
        ai_state={},
        conversation_history=[],
    )
    db.add(solution)
    await db.flush()
    return solution


@router.get("/workspace/{workspace_id}", response_model=list[SolutionResponse])
async def list_solutions(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Solution]:
    """List all solutions in a workspace."""
    # Verify workspace ownership
    ws_result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    if not ws_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workspace not found")

    result = await db.execute(
        select(Solution)
        .where(Solution.workspace_id == workspace_id)
        .order_by(Solution.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{solution_id}", response_model=SolutionDetailResponse)
async def get_solution(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SolutionDetailResponse:
    """Get solution details including all artifacts."""
    result = await db.execute(
        select(Solution)
        .options(selectinload(Solution.artifacts))
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    return SolutionDetailResponse(
        id=solution.id,
        workspace_id=solution.workspace_id,
        title=solution.title,
        description=solution.description,
        status=solution.status,
        approval_status=solution.approval_status,
        approved_by=solution.approved_by,
        approved_at=solution.approved_at,
        ai_state=solution.ai_state,
        conversation_history=solution.conversation_history,
        created_at=solution.created_at,
        updated_at=solution.updated_at,
        artifacts=[
            ArtifactResponse(
                id=a.id,
                solution_id=a.solution_id,
                artifact_type=a.artifact_type,
                title=a.title,
                content=a.content,
                content_text=a.content_text,
                version=a.version,
                created_at=a.created_at,
            )
            for a in solution.artifacts
        ],
    )


@router.delete("/{solution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_solution(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a solution and all its artifacts."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    await db.delete(solution)


@router.get("/{solution_id}/decisions")
async def get_solution_decisions(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the aggregated decision record log across all solution artifacts."""
    result = await db.execute(
        select(Solution)
        .options(selectinload(Solution.artifacts))
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    decisions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 1. Decisions recorded in AI state
    ai_state = solution.ai_state or {}
    for dec in ai_state.get("decisions", []):
        d_id = dec.get("id") or dec.get("topic")
        if d_id and d_id not in seen_ids:
            seen_ids.add(d_id)
            decisions.append(dec)

    # 2. Decisions attached to artifacts
    for art in solution.artifacts:
        art_content = art.content or {}
        for dec in art_content.get("decisions", []):
            d_id = dec.get("id") or dec.get("topic")
            if d_id and d_id not in seen_ids:
                seen_ids.add(d_id)
                decisions.append(dec)

    return {
        "solution_id": str(solution.id),
        "title": solution.title,
        "total_decisions": len(decisions),
        "decisions": decisions,
        "assumptions_log": ai_state.get("assumptions_log", []),
        "requirements": ai_state.get("requirements", []),
    }


class RequestChangesPayload(BaseModel):
    comments: str


class CascadingRegeneratePayload(BaseModel):
    targets: list[str]
    feedback: str = ""
    cascade: bool = True
    # When true, only computes the impact (affected artifacts + credit quote) and
    # does NOT mutate staleness. Used by the "Impact Preview" modal.
    dry_run: bool = False


class UIThemePayload(BaseModel):
    primary_color: str | None = None
    font_family: str | None = None
    border_radius: str | None = None
    density: str | None = None
    extra_tokens: dict[str, Any] | None = None


@router.post("/{solution_id}/approve")
async def approve_solution(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Approve the blueprint, freezing artifact versions and permitting MVP build."""
    from datetime import UTC, datetime

    if current_user.role not in ("owner", "admin", "approver"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approver, admin, or owner role required to approve blueprints",
        )

    result = await db.execute(
        select(Solution)
        .options(selectinload(Solution.artifacts))
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    snapshot = {
        str(art.id): {
            "artifact_type": art.artifact_type,
            "version": art.version,
            "title": art.title,
        }
        for art in solution.artifacts
    }

    solution.status = "approved"
    solution.approval_status = "approved"
    solution.approved_by = current_user.id
    solution.approved_at = datetime.now(UTC)
    solution.approval_snapshot = snapshot
    await db.commit()

    return {
        "status": "approved",
        "approval_status": "approved",
        "solution_id": str(solution.id),
        "approved_by": str(current_user.id),
        "approved_at": solution.approved_at.isoformat(),
        "artifacts_snapshotted": len(snapshot),
    }


@router.post("/{solution_id}/request-changes")
async def request_changes(
    solution_id: UUID,
    payload: RequestChangesPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Request changes on the solution blueprint with review feedback."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    solution.status = "changes_requested"
    solution.approval_status = "changes_requested"
    solution.approval_comments = payload.comments
    await db.commit()

    return {
        "status": "changes_requested",
        "approval_status": "changes_requested",
        "solution_id": str(solution.id),
        "comments": payload.comments,
    }


@router.post("/{solution_id}/regenerate")
async def cascade_regenerate(
    solution_id: UUID,
    payload: CascadingRegeneratePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Calculate cascading regeneration impact and mark affected downstream artifacts stale."""
    from app.services.artifact_graph import (
        get_downstream,
        mark_dependents_stale,
        normalize_artifact_type,
    )

    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    targets = [normalize_artifact_type(t) for t in payload.targets]

    all_affected: set[str] = set(targets)
    if payload.cascade:
        for target in targets:
            if payload.dry_run:
                # Pure impact computation — never writes to the database, so the
                # preview modal can be opened without corrupting staleness flags.
                all_affected.update(get_downstream(target))
            else:
                downstream = await mark_dependents_stale(db, solution.id, target)
                all_affected.update(downstream)

    credit_estimate = len(all_affected) * 2

    return {
        "status": "success",
        "solution_id": str(solution.id),
        "primary_targets": targets,
        "affected_artifacts": sorted(all_affected),
        "estimated_credits": credit_estimate,
        "cascade": payload.cascade,
        "dry_run": payload.dry_run,
    }


@router.patch("/{solution_id}/theme")
async def update_solution_theme(
    solution_id: UUID,
    payload: UIThemePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Customize UI/UX design tokens for wireframes and MVP template."""
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(
            Solution.id == solution_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    theme = dict(solution.ui_theme or {})
    if payload.primary_color:
        theme["primary_color"] = payload.primary_color
    if payload.font_family:
        theme["font_family"] = payload.font_family
    if payload.border_radius:
        theme["border_radius"] = payload.border_radius
    if payload.density:
        theme["density"] = payload.density
    if payload.extra_tokens:
        theme.update(payload.extra_tokens)

    solution.ui_theme = theme
    await db.commit()

    return {
        "status": "success",
        "solution_id": str(solution.id),
        "ui_theme": theme,
    }
