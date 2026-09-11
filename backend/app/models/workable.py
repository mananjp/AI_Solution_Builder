"""
AI Solution Builder — Workable Schema Registry

Tracks tenant-isolated PostgreSQL schemas provisioned by the
Workable System Runtime Engine (Section 5 of the implementation plan).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkableSchema(Base):
    __tablename__ = "workable_schemas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    modules: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list
    )  # [{module, entity, path}]
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="provisioning"
    )  # provisioning, provisioned, error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
