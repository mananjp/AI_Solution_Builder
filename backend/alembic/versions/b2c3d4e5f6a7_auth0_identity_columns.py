"""auth0 identity columns on users

Adds the columns Auth0-backed identity resolution needs and switches the
`auth_provider` default over. The API no longer stores passwords or mints its
own HS256 tokens, so `hashed_password` is deliberately left in place (always
NULL from here on): dropping a column is irreversible, and keeping it means a
rollback to the previous release still works.

Revision ID: b2c3d4e5f6a7
Revises: f3a4b5c6d7e8
Create Date: 2026-09-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(inspector: sa.Inspector) -> set[str]:
    return {c["name"] for c in inspector.get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        # Fresh install: the app lifespan runs create_all against the current
        # models, so there is nothing to patch.
        return

    columns = _columns(inspector)

    if "auth_issuer" not in columns:
        op.add_column("users", sa.Column("auth_issuer", sa.String(255), nullable=True))
        op.create_index("ix_users_auth_issuer", "users", ["auth_issuer"], unique=False)

    if "email_verified" not in columns:
        op.add_column(
            "users",
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        # Backfill from the email column, then drop the server default. Leaving a
        # permanent default of false would make a later failed verification
        # look like a successful one on any insert that omits the column.
        op.execute(
            sa.text(
                "UPDATE users SET email_verified = true WHERE email IS NOT NULL AND email <> ''"
            )
        )
        op.alter_column("users", "email_verified", server_default=None)

    # Identity is (issuer, sub), not sub alone: two tenants can mint the same
    # sub, and without the issuer a token from one tenant would resolve to a
    # user belonging to another. A plain unique constraint is safe here because
    # SQL treats NULLs as distinct, so legacy rows with no sub do not collide.
    unique_names = {c["name"] for c in inspector.get_unique_constraints("users")}
    if "uq_users_auth0_identity" not in unique_names:
        op.create_unique_constraint(
            "uq_users_auth0_identity",
            "users",
            ["auth_issuer", "provider_user_id"],
        )

    op.alter_column(
        "users",
        "auth_provider",
        server_default="auth0",
        existing_type=sa.String(50),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert the Auth0 scaffolding.

    This restores the schema but cannot restore the old behaviour: the code that
    created users with local passwords and minted HS256 tokens has been
    deleted, so this is a database rollback, not a return to password login.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    unique_names = {c["name"] for c in inspector.get_unique_constraints("users")}
    if "uq_users_auth0_identity" in unique_names:
        op.drop_constraint("uq_users_auth0_identity", "users", type_="unique")

    columns = _columns(inspector)
    if "email_verified" in columns:
        op.drop_column("users", "email_verified")
    if "auth_issuer" in columns:
        op.drop_index("ix_users_auth_issuer", table_name="users")
        op.drop_column("users", "auth_issuer")

    op.alter_column(
        "users",
        "auth_provider",
        server_default="local",
        existing_type=sa.String(50),
        existing_nullable=False,
    )
