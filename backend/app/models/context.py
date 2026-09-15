"""
AI Solution Builder — Context Chunk Model

pgvector-backed storage of chunked, embedded ingestion content
(Universal Input Ingestion Layer, Section 3 of the implementation plan).
Enables semantic search over uploaded context regardless of source format.
"""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base
from app.core.db_types import UUID


class ContextChunk(Base):
    __tablename__ = "context_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    solution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # document, url, conversation
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    detected_lang: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
