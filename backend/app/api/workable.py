"""
AI Solution Builder — Workable System Runtime API
(Section 5 of the implementation plan)

Routes for the live, provisioned systems:

    POST   /api/v1/workable/{solution_id}/provision
    GET    /api/v1/workable/{solution_id}/modules
    GET    /api/v1/workable/{solution_id}/seed?rows=N
    GET    /api/v1/workable/{solution_id}/{module}
    GET,POST,GET,PATCH,DELETE  .../{module}/{entity}[/{row_id}]
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.solution import Solution
from app.models.user import User
from app.models.workable import WorkableSchema
from app.models.workspace import Workspace
from app.schemas import ProvisionRequest
from app.services.synthetic import seed_synthetic_rows
from app.workable import engine as workable_engine
from app.workable.schema_provisioner import provision_workable_schema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workable", tags=["Workable Systems"])


async def _get_solution_for_user(db: AsyncSession, solution_id: UUID, user: User) -> Solution:
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == user.org_id)
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


async def _get_registered_schema(db: AsyncSession, solution_id: UUID, user: User) -> WorkableSchema:
    await _get_solution_for_user(db, solution_id, user)
    result = await db.execute(
        select(WorkableSchema).where(WorkableSchema.solution_id == solution_id)
    )
    registered = result.scalar_one_or_none()
    if not registered:
        raise HTTPException(status_code=404, detail="Workable system not provisioned yet")
    if registered.status != "provisioned":
        raise HTTPException(
            status_code=409,
            detail=f"Workable system status is '{registered.status}'",
        )
    return registered


@router.post("/{solution_id}/provision")
async def provision(
    solution_id: UUID,
    payload: ProvisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Provision the tenant schema + tables for a solution (idempotent)."""
    solution = await _get_solution_for_user(db, solution_id, current_user)
    try:
        registered = await provision_workable_schema(db, solution)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {
        "solution_id": str(solution_id),
        "schema_name": registered.schema_name,
        "status": registered.status,
        "modules": registered.modules,
    }


@router.get("/{solution_id}/modules")
async def list_modules(
    solution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List provisioned modules and their entity tables."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    return {
        "solution_id": str(solution_id),
        "schema_name": registered.schema_name,
        "status": registered.status,
        "modules": registered.modules,
    }


@router.post("/{solution_id}/seed")
async def seed_data(
    solution_id: UUID,
    rows: int = Query(5, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate realistic synthetic rows in the provisioned tables."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    created = await seed_synthetic_rows(db, registered.schema_name, registered.modules, rows)
    await db.commit()
    return {"seeded": created, "per_table": rows}


@router.get("/{solution_id}/{module_name}")
async def module_index(
    solution_id: UUID,
    module_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the entities and record counts for a module."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    module = next((m for m in registered.modules or [] if m["module"] == module_name), None)
    if not module:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    counts: dict[str, int] = {}
    for entity in module.get("entities", []):
        table = await workable_engine.resolve_table(db, registered.schema_name, entity)
        total = (await db.execute(select(func.count()).select_from(table))).scalar() or 0
        counts[entity] = int(total)
    return {
        "module": module_name,
        "path": module.get("path"),
        "entities": module.get("entities"),
        "counts": counts,
    }


@router.get("/{solution_id}/{module_name}/{entity}")
async def list_records(
    solution_id: UUID,
    module_name: str,
    entity: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List records for an entity table (paginated)."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    _ensure_entity(registered, module_name, entity)
    return await workable_engine.list_rows(db, registered.schema_name, entity, page, page_size)


@router.post("/{solution_id}/{module_name}/{entity}")
async def create_record(
    solution_id: UUID,
    module_name: str,
    entity: str,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a record in an entity table (validated against the live schema)."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    _ensure_entity(registered, module_name, entity)
    table = await workable_engine.resolve_table(db, registered.schema_name, entity)
    model = workable_engine.build_create_model(table)
    validated = model(**payload)
    result = await workable_engine.create_row(
        db, registered.schema_name, entity, validated.model_dump()
    )
    await db.commit()
    return result


@router.get("/{solution_id}/{module_name}/{entity}/{row_id}")
async def get_record(
    solution_id: UUID,
    module_name: str,
    entity: str,
    row_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single record by primary key."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    _ensure_entity(registered, module_name, entity)
    return await workable_engine.get_row(db, registered.schema_name, entity, row_id)


@router.patch("/{solution_id}/{module_name}/{entity}/{row_id}")
async def update_record(
    solution_id: UUID,
    module_name: str,
    entity: str,
    row_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Partially update a record."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    _ensure_entity(registered, module_name, entity)
    result = await workable_engine.update_row(db, registered.schema_name, entity, row_id, payload)
    await db.commit()
    return result


@router.delete("/{solution_id}/{module_name}/{entity}/{row_id}", status_code=204)
async def delete_record(
    solution_id: UUID,
    module_name: str,
    entity: str,
    row_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a record by primary key."""
    registered = await _get_registered_schema(db, solution_id, current_user)
    _ensure_entity(registered, module_name, entity)
    await workable_engine.delete_row(db, registered.schema_name, entity, row_id)
    await db.commit()


def _ensure_entity(registered: WorkableSchema, module_name: str, entity: str) -> None:
    module = next((m for m in registered.modules or [] if m["module"] == module_name), None)
    if not module:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")
    if entity not in (module.get("entities") or []):
        raise HTTPException(
            status_code=404,
            detail=f"Entity '{entity}' is not part of module '{module_name}'",
        )
