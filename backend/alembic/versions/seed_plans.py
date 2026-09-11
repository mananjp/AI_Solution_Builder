"""seed plans

Revision ID: seed_plans
Revises: 659ce2bb944d
Create Date: 2026-09-10

Seeds the monetization plans (Section 13 of the implementation plan):
free (200 credits / 1 system), pro (2000 / 5), enterprise (custom / unlimited).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "seed_plans"
down_revision: str | None = "659ce2bb944d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO plans (id, name, monthly_credits, max_workable_systems, price_usd, created_at)
        VALUES
            (gen_random_uuid(), 'free', 200, 1, 0.00, NOW()),
            (gen_random_uuid(), 'pro', 2000, 5, 49.00, NOW()),
            (gen_random_uuid(), 'enterprise', 999999, 999999, 0.00, NOW())
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE name IN ('free', 'pro', 'enterprise')")
