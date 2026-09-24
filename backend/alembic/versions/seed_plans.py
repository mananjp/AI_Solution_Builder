"""seed plans

Revision ID: seed_plans
Revises: 659ce2bb944d
Create Date: 2026-09-10

Seeds the monetization plans (Section 13 of the implementation plan):
free (200 credits / 1 system), pro (2000 / 5), enterprise (custom / unlimited).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "seed_plans"
down_revision: str | None = "659ce2bb944d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Dialect-portable upsert: generate PKs and timestamps in Python so the same
    # migration runs on Postgres and SQLite (gen_random_uuid()/NOW() are PG-only),
    # and only insert rows that are not already present (on_conflict is
    # dialect-specific and unavailable on a generic sa.table().insert()).
    plans: tuple[tuple[str, int, int, float], ...] = (
        ("free", 200, 1, 0.0),
        ("pro", 2000, 5, 49.0),
        ("enterprise", 999999, 999999, 0.0),
    )
    now = datetime.now(UTC)
    bind = op.get_bind()
    plans_table = sa.table(
        "plans",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String(50)),
        sa.column("monthly_credits", sa.Integer()),
        sa.column("max_workable_systems", sa.Integer()),
        sa.column("price_usd", sa.Numeric(10, 2)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    existing = {row[0] for row in bind.execute(sa.text("SELECT name FROM plans")).fetchall()}
    for name, monthly_credits, max_workable_systems, price_usd in plans:
        if name in existing:
            continue
        bind.execute(
            plans_table.insert().values(
                id=uuid.uuid4(),
                name=name,
                monthly_credits=monthly_credits,
                max_workable_systems=max_workable_systems,
                price_usd=price_usd,
                created_at=now,
            )
        )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE name IN ('free', 'pro', 'enterprise')")
