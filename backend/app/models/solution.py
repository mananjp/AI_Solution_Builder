"""
AI Solution Builder — Solution Model

Represents a single AI-generated solution within a workspace.
Stores the full AI pipeline state as JSON for resumability.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )  # draft, clarifying, blueprint_ready, approved, building, built, deployed, live, changes_requested
    approval_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )  # pending, approved, changes_requested
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    ui_theme: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=dict)
    ai_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    conversation_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default=list
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
    workspace = relationship("Workspace", back_populates="solutions")
    artifacts = relationship(
        "SolutionArtifact", back_populates="solution", cascade="all, delete-orphan"
    )
