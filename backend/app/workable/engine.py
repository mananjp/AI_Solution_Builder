"""
AI Solution Builder — Workable System Runtime Engine: Headless REST
(Section 5 of the implementation plan)

Provides generic, introspection-driven CRUD over provisioned tenant schemas.
For every registered module/entity it resolves the live table, builds a
dynamic Pydantic model from the real columns, and exposes list/create/get/
update/delete operations through a single set of routes.
"""

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

from fastapi import HTTPException
from pydantic import BaseModel, create_model
from sqlalchemy import Column, MetaData, Table, delete, func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine

logger = logging.getLogger(__name__)

_PAGINATION_MAX = 100


# ── Column → Python type mapping ──────────────────
def _python_type_for_column(col: Column[Any]) -> type[Any]:
    col_type = str(col.type).upper()
    if "UUID" in col_type:
        return str
    if "VARCHAR" in col_type or "CHAR" in col_type or "TEXT" in col_type:
        return str
    if "INT" in col_type:
        return int
    if any(t in col_type for t in ("NUMERIC", "DECIMAL", "FLOAT", "DOUBLE")):
        return float
    if "BOOL" in col_type:
        return bool
    if "TIMESTAMP" in col_type or "DATE" in col_type:
        return str
    if "JSON" in col_type:
        return dict
    return str


def _is_server_generated(col: Column[Any]) -> bool:
    """Columns we skip on create (identity, server defaults, uuid defaults)."""
    if col.primary_key:
        return True
    return col.server_default is not None or col.default is not None


def _row_to_json(row: Any) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in row._mapping.items()}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


# ── Schema / column introspection ─────────────────
async def _table_for(db: AsyncSession, schema_name: str, table_name: str) -> Table:
    def load_tables(sync_conn: Connection) -> tuple[MetaData, Table]:
        meta = MetaData(schema=schema_name)
        try:
            table = Table(table_name, meta, autoload_with=sync_conn)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Entity '{table_name}' not found") from exc
        return meta, table

    conn = await engine.connect()
    try:
        _meta, table = await conn.run_sync(load_tables)
        return table
    finally:
        await conn.close()


async def resolve_table(db: AsyncSession, schema_name: str, table_name: str) -> Table:
    """Public entry point to introspect a provisioned entity table."""
    return await _table_for(db, schema_name, table_name)


def _primary_key(table: Table) -> Column[Any]:
    pks = [c for c in table.columns if c.primary_key]
    if not pks:
        raise HTTPException(status_code=400, detail=f"Table '{table.name}' has no primary key")
    if len(pks) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table.name}' has a composite primary key — unsupported",
        )
    return pks[0]


def _annotation_for(col: Column[Any], required: bool) -> tuple[Any, Any]:
    """Pydantic (annotation, default) pair, honouring optionality."""
    py_type = _python_type_for_column(col)
    annotation: Any = py_type if required else py_type | None
    return (annotation, ... if required else None)  # type: ignore[misc]


def build_create_model(table: Table) -> type[BaseModel]:
    """Dynamic Pydantic model for inserts (drops server-generated columns)."""
    fields: dict[str, tuple[Any, Any]] = {}
    for col in table.columns:
        if _is_server_generated(col) or col.name == "id":
            continue
        fields[col.name] = _annotation_for(col, required=bool(not col.nullable))
    return cast(
        type[BaseModel],
        create_model(f"Create{table.name.capitalize()}", **cast(dict[str, Any], fields)),
    )


def build_update_model(table: Table) -> type[BaseModel]:
    """Dynamic Pydantic model for partial updates (all optional)."""
    fields: dict[str, tuple[Any, Any]] = {}
    for col in table.columns:
        if col.name == "id":
            continue
        fields[col.name] = _annotation_for(col, required=False)
    return cast(
        type[BaseModel],
        create_model(f"Update{table.name.capitalize()}", **cast(dict[str, Any], fields)),
    )


# ── CRUD operations ───────────────────────────────
async def list_rows(
    db: AsyncSession,
    schema_name: str,
    table_name: str,
    page: int = 1,
    page_size: int = 20,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    table = await _table_for(db, schema_name, table_name)
    page_size = min(max(1, page_size), _PAGINATION_MAX)
    offset = max(0, (page - 1) * page_size)
    where = _where_clause(table, filters or {})

    count_stmt = select(func.count()).select_from(table)
    if where is not None:
        count_stmt = count_stmt.where(*where)
    total = (await db.execute(count_stmt)).scalar() or 0

    # Order by the real primary key — the generated schemas don't always name it
    # `id` (e.g. `order_id`, `customer_id`), and table.c.id would crash.
    pk_col = _primary_key(table)
    stmt = select(table).order_by(pk_col).offset(offset).limit(page_size)
    if where is not None:
        stmt = stmt.where(*where)
    result = await db.execute(stmt)
    items = [_row_to_json(row) for row in result.all()]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "pages": (int(total) + page_size - 1) // page_size,
    }


async def get_row(
    db: AsyncSession, schema_name: str, table_name: str, row_id: str
) -> dict[str, Any]:
    table = await _table_for(db, schema_name, table_name)
    pk = _primary_key(table)
    result = await db.execute(select(table).where(pk == _coerce_id(pk, row_id)))
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Record not found in '{table_name}'")
    return _row_to_json(row)


async def create_row(
    db: AsyncSession, schema_name: str, table_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    table = await _table_for(db, schema_name, table_name)
    values = {key: value for key, value in payload.items() if key in table.c}
    stmt = insert(table).values(**values).returning(*table.c)
    result = await db.execute(stmt)
    await db.flush()
    row = result.first()
    if row is None:
        raise HTTPException(status_code=400, detail=f"Insert into '{table_name}' returned no row")
    return _row_to_json(row)


async def update_row(
    db: AsyncSession,
    schema_name: str,
    table_name: str,
    row_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    table = await _table_for(db, schema_name, table_name)
    pk = _primary_key(table)
    values = {key: value for key, value in payload.items() if key in table.c}
    stmt = select(table).where(pk == _coerce_id(pk, row_id))
    existing = (await db.execute(stmt)).first()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Record not found in '{table_name}'")

    if values:
        result = await db.execute(
            update(table).where(pk == _coerce_id(pk, row_id)).values(**values).returning(*table.c)
        )
        await db.flush()
        row = result.first()
    else:
        row = existing
    return _row_to_json(row)


async def delete_row(db: AsyncSession, schema_name: str, table_name: str, row_id: str) -> None:
    table = await _table_for(db, schema_name, table_name)
    pk = _primary_key(table)
    nresult = await db.execute(
        select(func.count()).select_from(table).where(pk == _coerce_id(pk, row_id))
    )
    if (nresult.scalar() or 0) == 0:
        raise HTTPException(status_code=404, detail=f"Record not found in '{table_name}'")
    await db.execute(delete(table).where(pk == _coerce_id(pk, row_id)))
    await db.flush()


def _coerce_id(pk: Column[Any], row_id: str) -> Any:
    col_type = str(pk.type).upper()
    if "UUID" in col_type:
        try:
            return uuid.UUID(str(row_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID for record id") from None
    if "INT" in col_type:
        try:
            return int(row_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid integer for record id") from None
    return row_id


def _where_clause(table: Table, filters: dict[str, Any]) -> list[Any] | None:
    conds = []
    for key, value in filters.items():
        if key in table.c and value is not None and value != "":
            conds.append(table.c[key] == value)
    return conds or None
