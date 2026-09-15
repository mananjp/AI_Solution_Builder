"""
AI Solution Builder — Solution Artifact Model

Stores individual generated artifacts (HLD, wireframes, ER diagrams, etc.)
with version control — every write creates a new version with a parent pointer.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import JSONB, UUID


class SolutionArtifact(Base):
    __tablename__ = "solution_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solutions.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # hld, lld, wireframe, er_diagram, bpmn, roadmap, api_spec, database_schema
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=True)  # Rendered markdown/text version
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solution_artifacts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    solution = relationship("Solution", back_populates="artifacts")
    comments = relationship(
        "ArtifactComment", back_populates="artifact", cascade="all, delete-orphan"
    )


class ArtifactComment(Base):
    __tablename__ = "artifact_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solution_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    artifact = relationship("SolutionArtifact", back_populates="comments")
