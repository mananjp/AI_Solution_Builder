"""
AI Solution Builder — Recommendation Event Model

Logs every time the Business Recommendation Agent proposes modules,
and what the user accepted — feeds back into the Industry Template Library.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.db_types import JSONB, UUID


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    industry_classified: Mapped[str] = mapped_column(String(100), nullable=True)
    modules_proposed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True)
    modules_accepted: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
