"""create payment_orders for gateway checkout attribution

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-09-23 12:00:00.000000

Stores the gateway order id → org/credits mapping so webhooks can credit the
correct organization idempotently.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type(bind) -> sa.types.TypeEngine:
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_orders" in inspector.get_table_names():
        return

    uuid_t = _uuid_type(bind)
    op.create_table(
        "payment_orders",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("gateway", sa.String(20), nullable=False, server_default="razorpay"),
        sa.Column("gateway_order_id", sa.String(64), nullable=False),
        sa.Column("org_id", uuid_t, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_orders_gateway_order_id", "payment_orders", ["gateway_order_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_orders" not in inspector.get_table_names():
        return
    op.drop_index("ix_payment_orders_gateway_order_id", table_name="payment_orders")
    op.drop_table("payment_orders")