"""
AI Solution Builder — Row-Level Security helper (Section 8 / 15)

Opt-in multi-tenant isolation at the database layer. When RLS_ENABLED is on,
every table in a provisioned workable schema that carries an ``org_id``
column is locked down so rows are only visible when the connection's
``app.org_id`` setting matches the row's ``org_id``.
"""

import logging
from typing import Any

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


def build_policy_sql(schema_name: str, table_name: str) -> list[str]:
    """Return the statements that enable org-isolating RLS on one table."""
    qualified = f'"{schema_name}"."{table_name}"'
    return [
        f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY",
        (
            f'CREATE POLICY "org_isolation" ON {qualified} '
            "USING (org_id = COALESCE(NULLIF(current_setting('app.org_id', true), '')::uuid, '00000000-0000-0000-0000-000000000000'::uuid)) "
            "WITH CHECK (org_id = COALESCE(NULLIF(current_setting('app.org_id', true), '')::uuid, '00000000-0000-0000-0000-000000000000'::uuid))"
        ),
        f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY",
    ]


def tables_with_org_column(columns: list[tuple[str, str]]) -> list[str]:
    """Filter (table_name, column_name) pairs to tables exposing ``org_id``."""
    return [table for table, column in columns if column == "org_id"]


async def enable_org_rls(conn: Any, schema_name: str, org_id: str) -> None:
    """Enable org RLS on every table in the schema that has an ``org_id`` column.

    Runs within the caller's transaction; ``conn`` must be a connection that
    supports ``await conn.execute(sa_text(...))``.
    """
    rows = (
        await conn.execute(
            sa_text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND column_name = 'org_id'"
            ),
            {"schema": schema_name},
        )
    ).all()
    tables = tables_with_org_column(list(rows))
    for table in tables:
        for statement in build_policy_sql(schema_name, table):
            try:
                await conn.execute(sa_text(statement))
            except Exception as exc:  # tolerate non-supportive table types
                logger.warning("RLS policy failed for %s.%s: %s", schema_name, table, exc)
    if tables:
        logger.info("RLS enabled on %d table(s) in schema %s", len(tables), schema_name)


async def set_request_org(conn: Any, org_id: str) -> None:
    """Set the session-local ``app.org_id`` GUC for the current transaction.

    RLS policies read this value to filter rows per tenant. Use ``is_local=True``
    so the setting only applies within the request transaction.
    """
    await conn.execute(
        sa_text("SELECT set_config('app.org_id', :org_id, true)"),
        {"org_id": str(org_id)},
    )
