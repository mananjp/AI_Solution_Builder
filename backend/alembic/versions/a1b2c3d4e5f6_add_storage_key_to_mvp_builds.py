"""add storage_key to mvp_builds

Revision ID: a1b2c3d4e5f6
Revises: seed_plans
Create Date: 2026-09-12 13:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "seed_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mvp_builds", sa.Column("storage_key", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("mvp_builds", "storage_key")
