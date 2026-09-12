"""create mvp_builds table

Revision ID: b1a2c3d4e5f6
Revises: seed_plans
Create Date: 2026-09-12 14:00:00.000000

Creates the mvp_builds table that was missed from the initial_schema
migration.  Uses an inspector guard so it's idempotent on dev databases
where Base.metadata.create_all() already ran at app startup.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: str | None = "seed_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("mvp_builds"):
        return

    op.create_table(
        "mvp_builds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("solution_id", sa.UUID(), nullable=False),
        sa.Column("build_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("opencode_session_id", sa.String(length=255), nullable=True),
        sa.Column("workspace_path", sa.String(length=1000), nullable=False),
        sa.Column(
            "app_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repo_url", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["solution_id"], ["solutions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("solution_id", "build_number", name="uq_mvp_build_solution_number"),
    )
    op.create_index(
        op.f("ix_mvp_builds_solution_id"),
        "mvp_builds",
        ["solution_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("mvp_builds"):
        return
    op.drop_index(op.f("ix_mvp_builds_solution_id"), table_name="mvp_builds")
    op.drop_table("mvp_builds")
