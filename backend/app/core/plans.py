"""
AI Solution Builder — Default Monetization Plans

Idempotent, dialect-portable seeding of the built-in plans (Section 13 of the
implementation plan). Used by the app lifespan, Alembic migrations, and the lazy
get-or-create paths in auth so the ``plans`` table is never missing at runtime.
"""

from typing import Any, cast

from sqlalchemy import Result, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import Plan

# (name, monthly_credits, max_workable_systems, price_usd)
DEFAULT_PLANS: tuple[tuple[str, int, int, float], ...] = (
    ("free", 200, 1, 0.0),
    ("pro", 2000, 5, 49.0),
    ("enterprise", 999999, 999999, 0.0),
)


def _plan_rows() -> list[dict[str, int | str | float]]:
    return [
        {
            "name": name,
            "monthly_credits": monthly_credits,
            "max_workable_systems": max_workable_systems,
            "price_usd": price_usd,
        }
        for name, monthly_credits, max_workable_systems, price_usd in DEFAULT_PLANS
    ]


async def ensure_default_plans(db: AsyncSession) -> None:
    """Async-session variant: create the default plans if missing (idempotent)."""
    for spec in _plan_rows():
        exists = (
            await db.execute(select(Plan.id).where(Plan.name == spec["name"]))
        ).scalar_one_or_none()
        if exists is None:
            db.add(Plan(**spec))
    await db.flush()


def ensure_default_plans_sync(conn: Connection) -> None:
    """Sync variant for use inside ``conn.run_sync`` in the lifespan.

    ``Connection`` has no ORM session methods (``add``/``flush``), so seeding
    uses Core ``insert`` statements guarded by a per-row existence check. The
    surrounding ``engine.begin()`` transaction flushes the writes on commit.
    """
    for spec in _plan_rows():
        exists = conn.execute(
            select(Plan.id).where(Plan.name == spec["name"])
        ).scalar_one_or_none()
        if exists is None:
            conn.execute(insert(Plan).values(**spec))


async def get_or_create_free_plan(db: AsyncSession) -> Plan:
    """Return the ``free`` plan, creating it if absent (safe under concurrency).

    The SELECT-then-INSERT sequence can race with a concurrent request that creates
    the plan between the two calls, so a unique-constraint violation on ``name`` is
    recovered by rolling back the failed INSERT and re-selecting. This helper is only
    ever called before other rows are written in the surrounding transaction, so the
    rollback never discards user/org data.
    """
    result: Result[Any] = await db.execute(select(Plan).where(Plan.name == "free"))
    plan = cast("Plan | None", result.scalar_one_or_none())
    if plan is not None:
        return plan

    db.add(Plan(monthly_credits=200, max_workable_systems=1, price_usd=0, name="free"))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(select(Plan).where(Plan.name == "free"))
        plan = cast("Plan | None", result.scalar_one_or_none())
        if plan is None:
            raise
    assert plan is not None
    return plan
