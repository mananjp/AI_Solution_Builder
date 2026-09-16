"""
AI Solution Builder — Organization Model

Multi-tenant organization entity. Each org has its own
workspaces, users, and credit balance.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True
    )
    # NULL credits_remaining means unlimited credits (e.g. demo account).
    credits_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True, default=200)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    users = relationship("User", back_populates="organization")
    workspaces = relationship("Workspace", back_populates="organization")
    plan = relationship("Plan")
