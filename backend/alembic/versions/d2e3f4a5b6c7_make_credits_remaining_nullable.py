"""make credits_remaining nullable for unlimited accounts

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-16 12:00:00.000000

Allows organizations to have NULL credits_remaining, which is interpreted
as "unlimited credits" throughout the application.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("organizations", "credits_remaining", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE organizations SET credits_remaining = 0 WHERE credits_remaining IS NULL")
    op.alter_column("organizations", "credits_remaining", nullable=False)
