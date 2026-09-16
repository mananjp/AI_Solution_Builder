"""add file_list to mvp_builds and users.settings schema sync

Revision ID: e7f8a9b0c1d2
Revises: d2e3f4a5b6c7
Create Date: 2026-09-16 12:00:00.000000

Stores the generated MVP file manifest in the database so the API service
can list/download build contents purely from Cloudinary + PostgreSQL
without reading the builder service's local filesystem. Also creates the
``users.settings`` JSONB column that the ORM model has always declared but
no earlier migration added.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("mvp_builds")]
    if "file_list" not in columns:
        op.add_column(
            "mvp_builds",
            sa.Column("file_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    # Model drift fix: users.settings (JSONB) exists on the ORM model but was
    # never created by any earlier migration; add it if a pre-existing schema
    # predates it.
    user_cols = [col["name"] for col in inspector.get_columns("users")]
    if "settings" not in user_cols:
        op.add_column(
            "users",
            sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("mvp_builds")]
    if "file_list" in columns:
        op.drop_column("mvp_builds", "file_list")
    user_cols = [col["name"] for col in inspector.get_columns("users")]
    if "settings" in user_cols:
        op.drop_column("users", "settings")
