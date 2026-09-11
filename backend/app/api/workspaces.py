"""
AI Solution Builder — Workspace API Routes

CRUD operations for workspaces, scoped to the user's organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("/", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    """List all workspaces in the user's organization."""
    result = await db.execute(
        select(
            Workspace,
            func.count(Solution.id).label("solution_count"),
        )
        .outerjoin(Solution, Solution.workspace_id == Workspace.id)
        .where(Workspace.org_id == current_user.org_id)
        .group_by(Workspace.id)
        .order_by(Workspace.created_at.desc())
    )
    rows = result.all()
    return [
        WorkspaceResponse(
            id=ws.id,
            org_id=ws.org_id,
            name=ws.name,
            description=ws.description,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            solution_count=count,
        )
        for ws, count in rows
    ]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Create a new workspace in the user's organization."""
    workspace = Workspace(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(workspace)
    await db.flush()
    return WorkspaceResponse(
        id=workspace.id,
        org_id=workspace.org_id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        solution_count=0,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Get a specific workspace by ID."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Count solutions
    count_result = await db.execute(
        select(func.count(Solution.id)).where(Solution.workspace_id == workspace_id)
    )
    count = count_result.scalar() or 0

    return WorkspaceResponse(
        id=workspace.id,
        org_id=workspace.org_id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        solution_count=count,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Update a workspace's name or description."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if payload.name is not None:
        workspace.name = payload.name
    if payload.description is not None:
        workspace.description = payload.description

    await db.flush()
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workspace and all its solutions."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.org_id == current_user.org_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await db.delete(workspace)
