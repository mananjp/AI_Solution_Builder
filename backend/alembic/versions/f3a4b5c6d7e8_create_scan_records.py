"""create scan_records table for threat scanning audit and reporting

Revision ID: f3a4b5c6d7e8
Revises: a3b4c5d6e7f8
Create Date: 2026-09-26 12:00:00.000000

Stores verdicts, findings, and telemetry for threat scan events across all layers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type(bind) -> sa.types.TypeEngine:
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)


def _json_type(bind) -> sa.types.TypeEngine:
    return postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scan_records" in inspector.get_table_names():
        return

    uuid_t = _uuid_type(bind)
    json_t = _json_type(bind)

    op.create_table(
        "scan_records",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("target", sa.String(10), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("findings", json_t, nullable=False),
        sa.Column("scanned_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("from_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_id", uuid_t, nullable=True),
        sa.Column("org_id", uuid_t, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_scan_records_sha256", "scan_records", ["sha256"])
    op.create_index("ix_scan_records_source", "scan_records", ["source"])
    op.create_index("ix_scan_records_verdict", "scan_records", ["verdict"])
    op.create_index("ix_scan_records_user_id", "scan_records", ["user_id"])
    op.create_index("ix_scan_records_org_id", "scan_records", ["org_id"])
    op.create_index("ix_scan_records_created_at", "scan_records", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scan_records" not in inspector.get_table_names():
        return

    op.drop_index("ix_scan_records_created_at", table_name="scan_records")
    op.drop_index("ix_scan_records_org_id", table_name="scan_records")
    op.drop_index("ix_scan_records_user_id", table_name="scan_records")
    op.drop_index("ix_scan_records_verdict", table_name="scan_records")
    op.drop_index("ix_scan_records_source", table_name="scan_records")
    op.drop_index("ix_scan_records_sha256", table_name="scan_records")
    op.drop_table("scan_records")
