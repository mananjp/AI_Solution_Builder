"""create build_jobs and oauth fields

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create build_jobs table if it does not exist
    if "build_jobs" not in tables:
        op.create_table(
            "build_jobs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True)
                if bind.dialect.name == "postgresql"
                else sa.String(36),
                primary_key=True,
            ),
            sa.Column(
                "build_id",
                postgresql.UUID(as_uuid=True)
                if bind.dialect.name == "postgresql"
                else sa.String(36),
                sa.ForeignKey("mvp_builds.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("claimed_by", sa.String(255), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_build_jobs_build_id", "build_jobs", ["build_id"])
        op.create_index("ix_build_jobs_status", "build_jobs", ["status"])
        op.create_index("ix_build_jobs_created_at", "build_jobs", ["created_at"])

    # 2. Add OAuth & Anonymous columns to users table
    user_cols = [col["name"] for col in inspector.get_columns("users")]
    if "auth_provider" not in user_cols:
        op.add_column(
            "users",
            sa.Column("auth_provider", sa.String(50), nullable=False, server_default="local"),
        )
    if "provider_user_id" not in user_cols:
        op.add_column(
            "users",
            sa.Column("provider_user_id", sa.String(255), nullable=True),
        )
        op.create_index("ix_users_provider_user_id", "users", ["provider_user_id"])
    if "is_anonymous" not in user_cols:
        op.add_column(
            "users",
            sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # 3. Make users.hashed_password nullable
    if "hashed_password" in user_cols:
        op.alter_column(
            "users",
            "hashed_password",
            existing_type=sa.String(255),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "build_jobs" in tables:
        op.drop_table("build_jobs")

    user_cols = [col["name"] for col in inspector.get_columns("users")]
    if "is_anonymous" in user_cols:
        op.drop_column("users", "is_anonymous")
    if "provider_user_id" in user_cols:
        op.drop_index("ix_users_provider_user_id", table_name="users")
        op.drop_column("users", "provider_user_id")
    if "auth_provider" in user_cols:
        op.drop_column("users", "auth_provider")
    if "hashed_password" in user_cols:
        op.alter_column(
            "users",
            "hashed_password",
            existing_type=sa.String(255),
            nullable=False,
        )
