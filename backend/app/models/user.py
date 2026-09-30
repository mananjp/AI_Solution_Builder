"""
AI Solution Builder - User Model

Local authorisation record for an Auth0 identity. Auth0 owns authentication
(who the person is); this table owns authorisation (what they may do): role,
organisation membership, settings and the encrypted deploy-secret vault.
Each user belongs to an organization.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Legacy. Always NULL now that Auth0 owns credentials; retained so an
    # existing database that still has the column keeps booting untouched.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="member"
    )  # owner, admin, approver, editor, member, viewer
    # "auth0" is the only value written going forward.
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="auth0")
    # The Auth0 `sub`, e.g. "auth0|65a1...". Unique per issuer rather than
    # globally: two tenants can mint the same sub, and the issuer is what
    # distinguishes them.
    provider_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # The tenant's `iss` claim. Scoping identity to (issuer, sub) means a token
    # from tenant A can never resolve to a User row belonging to tenant B.
    auth_issuer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    organization = relationship("Organization", back_populates="users")

    __table_args__ = (
        # Enforced in the database rather than only in application code, so a
        # race between two concurrent first-logins for the same Auth0 identity
        # cannot create two users. On Postgres this also backs the
        # get_current_user lookup, which was the hot path for every request.
        UniqueConstraint(
            "auth_issuer",
            "provider_user_id",
            name="uq_users_auth0_identity",
        ),
    )
