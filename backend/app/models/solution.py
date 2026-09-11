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
        String(50), nullable=False, default="discovery"
    )  # discovery, analyzing, generating, complete, error
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
