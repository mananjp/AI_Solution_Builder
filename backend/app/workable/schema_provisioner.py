"""
AI Solution Builder — Workable System Runtime Engine: Schema Provisioning
(Section 5 of the implementation plan)

Creates a tenant-isolated PostgreSQL schema per solution from the AI-generated
declarative schema / DDL, registers it in `workable_schemas`, and maps the
generated modules to their entity tables so the headless REST engine can
mount CRUD on top of real, operational tables.
"""

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine
from app.models.solution import Solution
from app.models.workable import WorkableSchema
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

_DDL_SPLIT_RE = re.compile(r";\s*(?=(?:[^']*'[^']*')*[^']*$)")


def _sanitize_schema_name(prefix: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", prefix.lower()) or "workable_default"


async def _list_tables(db: AsyncSession, schema_name: str) -> list[str]:
    result = await db.execute(
        sa_text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE' ORDER BY table_name"
        ),
        {"schema": schema_name},
    )
    return [row[0] for row in result.all()]


def _module_keywords(module_name: str) -> list[str]:
    return [part for part in module_name.lower().split("_") if len(part) >= 3]


def _assign_entities_to_modules(
    tables: list[str], modules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Map each entity table to a module.

    A table matches a module when its name is in the module's `entities` list
    or shares a keyword with the module name. Unassigned tables fall through
    to the first module.
    """
    if not modules:
        return [{"module": "default", "path": "/default", "entities": sorted(tables)}]

    keyword_map: list[tuple[str, list[str]]] = [
        (m["module"], _module_keywords(m["module"])) for m in modules
    ]
    ordered_modules = [m["module"] for m in modules]

    best: dict[str, list[str]] = {mod: [] for mod in ordered_modules}

    for table in tables:
        lowered = table.lower()
        target: str | None = None

        for module in modules:
            if lowered in {e.lower() for e in module.get("entities", [])}:
                target = module["module"]
                break
        if target is None:
            for mod, keywords in keyword_map:
                if keywords and any(k in lowered for k in keywords):
                    target = mod
                    break

        best[target or ordered_modules[0]].append(table)

    return [
        {
            "module": m["module"],
            "path": m.get("path", f"/{m['module']}"),
            "entities": sorted(best.get(m["module"], [])),
        }
        for m in modules
    ]


def _extract_schema_artifacts(
    solution: Solution,
) -> tuple[str | None, dict[str, Any]]:
    ai_state: dict[str, Any] = solution.ai_state or {}
    generated = ai_state.get("generated_schema")
    if not isinstance(generated, dict):
        return None, {}

    content = generated.get("content", {}) or {}
    ddl = content.get("ddl", "") or ""
    declarative = content.get("declarative", {}) or {}
    return ddl, {"tables": declarative.get("tables", [])}


async def provision_workable_schema(db: AsyncSession, solution: Solution) -> WorkableSchema:
    """Create (idempotently) the tenant schema for a solution and register it.

    Returns the WorkableSchema row (existing if already provisioned).
    Raises ValueError if the solution has no generated schema.
    """
    existing_row = (
        await db.execute(select(WorkableSchema).where(WorkableSchema.solution_id == solution.id))
    ).scalar_one_or_none()
    if existing_row is not None:
        return existing_row

    ddl, _decl = _extract_schema_artifacts(solution)
    modules_raw: list[dict[str, Any]] = (solution.ai_state or {}).get("workable_modules", []) or []

    schema_name = _sanitize_schema_name(f"workable_{solution.id.hex[:12]}")

    if not ddl:
        record = WorkableSchema(
            solution_id=solution.id,
            schema_name=schema_name,
            modules=[],
            status="error",
        )
        db.add(record)
        await db.flush()
        raise ValueError(
            "Solution has no generated schema DDL — cannot provision a workable system"
        )

    async with engine.begin() as conn:
        await conn.execute(sa_text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        await conn.execute(sa_text(f'SET search_path TO "{schema_name}", public'))

        statements = [s for s in _DDL_SPLIT_RE.split(ddl) if s and s.strip()]
        for statement in statements:
            try:
                await conn.execute(sa_text(statement.strip()))
            except Exception as exc:  # tolerate broken statements, keep the rest
                logger.warning("DDL statement failed in %s: %s", schema_name, exc)

        await conn.execute(sa_text("RESET search_path"))

        if settings.RLS_ENABLED:
            from app.services.rls import enable_org_rls

            org_id = (
                await db.execute(
                    select(Workspace.org_id).where(Workspace.id == solution.workspace_id)
                )
            ).scalar_one_or_none()
            if org_id is not None:
                await enable_org_rls(conn, schema_name, str(org_id))

    created_tables = await _list_tables(db, schema_name)
    modules = _assign_entities_to_modules(created_tables, modules_raw)

    record = WorkableSchema(
        solution_id=solution.id,
        schema_name=schema_name,
        modules=modules,
        status="provisioned" if created_tables else "error",
    )
    db.add(record)
    await db.flush()
    logger.info("Provisioned workable schema %s with tables: %s", schema_name, created_tables)
    return record
