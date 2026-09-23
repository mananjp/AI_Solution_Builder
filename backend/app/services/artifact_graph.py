"""
AI Solution Builder — Artifact Dependency Graph Service (P2)

Maintains the Directed Acyclic Graph (DAG) of artifact dependencies:
  requirements -> hld -> lld -> er_diagram -> database_schema -> api_spec -> code
                     |-> wireframes -----------------------------------|
                     |-> bpmn_flows

When an upstream artifact is regenerated, downstream artifacts can be marked stale
and cascading regenerations can be calculated.

``bpmn_flows`` is the canonical stored artifact type produced by the Process
Intelligence agent. ``bpmn`` was used by older UIs and is normalized here so both
names resolve to the same node.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import SolutionArtifact

ARTIFACT_DAG: dict[str, list[str]] = {
    "requirements": ["hld", "wireframe", "bpmn_flows"],
    "hld": ["lld", "wireframe", "bpmn_flows"],
    "lld": ["er_diagram"],
    "er_diagram": ["database_schema", "api_spec"],
    "database_schema": ["api_spec"],
    "wireframe": ["code"],
    "api_spec": ["code"],
    "bpmn_flows": [],
    "code": [],
}

_ARTIFACT_ALIASES: dict[str, str] = {
    "bpmn": "bpmn_flows",
}


def normalize_artifact_type(artifact_type: str) -> str:
    """Resolve legacy/UI artifact names to the canonical stored type."""
    return _ARTIFACT_ALIASES.get(artifact_type, artifact_type)


def get_downstream(artifact_type: str) -> list[str]:
    """Return all transitive downstream artifact types affected by changes to artifact_type."""
    root = normalize_artifact_type(artifact_type)
    visited: list[str] = []
    queue = list(ARTIFACT_DAG.get(root, []))

    while queue:
        current = queue.pop(0)
        if current not in visited:
            visited.append(current)
            queue.extend(ARTIFACT_DAG.get(current, []))

    return visited


def get_direct_downstream(artifact_type: str) -> list[str]:
    """Return directly dependent artifact types."""
    return list(ARTIFACT_DAG.get(normalize_artifact_type(artifact_type), []))


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
