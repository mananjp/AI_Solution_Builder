"""add solution approval and theme fields

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-09-22 18:50:00.000000

Adds lifecycle and governance columns to solutions:
approval_status, approved_by, approved_at, approval_comments,
approval_snapshot, and ui_theme.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("solutions")]

    if "approval_status" not in columns:
        op.add_column(
            "solutions",
            sa.Column("approval_status", sa.String(length=50), nullable=True),
        )

    if "approved_by" not in columns:
        op.add_column(
            "solutions",
            sa.Column(
                "approved_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )

    if "approved_at" not in columns:
        op.add_column(
            "solutions",
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "approval_comments" not in columns:
        op.add_column(
            "solutions",
            sa.Column("approval_comments", sa.Text(), nullable=True),
        )

    if "approval_snapshot" not in columns:
        op.add_column(
            "solutions",
            sa.Column(
                "approval_snapshot",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    if "ui_theme" not in columns:
        op.add_column(
            "solutions",
            sa.Column(
                "ui_theme",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("solutions", "ui_theme")
    op.drop_column("solutions", "approval_snapshot")
    op.drop_column("solutions", "approval_comments")
    op.drop_column("solutions", "approved_at")
    op.drop_column("solutions", "approved_by")
    op.drop_column("solutions", "approval_status")
