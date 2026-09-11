"""
AI Solution Builder — Solution API Routes

CRUD for solutions + artifact retrieval.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
