"""
AI Solution Builder — Artifact Dependency Graph Service (P2)

Maintains the Directed Acyclic Graph (DAG) of artifact dependencies:
  requirements -> hld -> lld -> er_diagram -> database_schema -> api_spec -> code
                     |-> wireframes -----------------------------------|
                     |-> bpmn

When an upstream artifact is regenerated, downstream artifacts can be marked stale
and cascading regenerations can be calculated.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import SolutionArtifact

ARTIFACT_DAG: dict[str, list[str]] = {
    "requirements": ["hld", "wireframe", "bpmn"],
    "hld": ["lld", "wireframe", "bpmn"],
    "lld": ["er_diagram"],
    "er_diagram": ["database_schema", "api_spec"],
    "database_schema": ["api_spec"],
    "wireframe": ["code"],
    "api_spec": ["code"],
    "bpmn": [],
    "code": [],
}


def get_downstream(artifact_type: str) -> list[str]:
    """Return all transitive downstream artifact types affected by changes to artifact_type."""
    visited: list[str] = []
    queue = list(ARTIFACT_DAG.get(artifact_type, []))

    while queue:
        current = queue.pop(0)
        if current not in visited:
            visited.append(current)
            queue.extend(ARTIFACT_DAG.get(current, []))

    return visited


def get_direct_downstream(artifact_type: str) -> list[str]:
    """Return directly dependent artifact types."""
    return list(ARTIFACT_DAG.get(artifact_type, []))


async def mark_dependents_stale(
    db: AsyncSession,
    solution_id: UUID,
    changed_artifact_type: str,
) -> list[str]:
    """Mark all downstream artifacts of changed_artifact_type as stale=True."""
    downstream_types = get_downstream(changed_artifact_type)
    if not downstream_types:
        return []

    # Query latest versions of downstream artifacts and flag them in content as stale
    stmt = select(SolutionArtifact).where(
        SolutionArtifact.solution_id == solution_id,
        SolutionArtifact.artifact_type.in_(downstream_types),
    )
    result = await db.execute(stmt)
    artifacts = result.scalars().all()

    for art in artifacts:
        content = dict(art.content or {})
        content["stale"] = True
        content["stale_reason"] = f"Upstream {changed_artifact_type} was modified"
        art.content = content

    await db.commit()
    return downstream_types
