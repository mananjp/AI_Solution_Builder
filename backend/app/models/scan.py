"""
AI Solution Builder — Threat Scan Record Model
(Phase 7.1 of Threat Scanning Implementation Plan SEC-SCAN-001)

Audit trail and telemetry record for every scan event.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScanRecord(Base):
    """Stores scan verdicts, findings, and telemetry for audit and admin reporting."""

    __tablename__ = "scan_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target: Mapped[str] = mapped_column(String(10), nullable=False)  # file, url, archive
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    scanned_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    from_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
