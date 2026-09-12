"""add storage_key to mvp_builds

Revision ID: a1b2c3d4e5f6
Revises: b1a2c3d4e5f6
Create Date: 2026-09-12 13:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("mvp_builds")]
    if "storage_key" not in columns:
        op.add_column("mvp_builds", sa.Column("storage_key", sa.String(1000), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("mvp_builds")]
    if "storage_key" in columns:
        op.drop_column("mvp_builds", "storage_key")
