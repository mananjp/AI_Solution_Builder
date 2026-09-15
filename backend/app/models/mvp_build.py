"""
AI Solution Builder — MVP Build Registry

Tracks OpenCode-driven MVP generation jobs (Section: OpenCode MVP Builder).
Each build is tied to a Solution and stored in a sandboxed workspace directory,
with the OpenCode sidecar session id captured for status polling and logs.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MVPBuild(Base):
    __tablename__ = "mvp_builds"
    __table_args__ = (
        UniqueConstraint("solution_id", "build_number", name="uq_mvp_build_solution_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    build_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending, building, complete, failed, cancelled
    opencode_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    app_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
