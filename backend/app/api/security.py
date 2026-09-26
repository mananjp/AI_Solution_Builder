"""
AI Solution Builder — Threat Scanning Admin & Observability API
(Phase 8 of Threat Scanning Implementation Plan SEC-SCAN-001)

Admin endpoints for inspecting scan audit records, metrics, scanner configuration,
and running on-demand file scans.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import check_admin, get_current_user
from app.models.scan import ScanRecord
from app.models.user import User
from app.services.legacy_repo.credentials import mask_secret
from app.services.security.clamav import ClamAVScanner
from app.services.security.orchestrator import scan_file
from app.services.security.virustotal import VirusTotalScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security Governance"])

_clamav_probe = ClamAVScanner()
_vt_probe = VirusTotalScanner()


@router.get("/scans")
async def list_scans(
    verdict: str | None = Query(
        None, description="Filter by verdict (clean, suspicious, malicious, etc.)"
    ),
    source: str | None = Query(
        None, description="Filter by source (upload.document, export.zip, etc.)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List recent threat scan audit records with optional filtering."""
    check_admin(current_user)

    stmt = select(ScanRecord).order_by(desc(ScanRecord.created_at))
    if verdict:
        stmt = stmt.where(ScanRecord.verdict == verdict)
    if source:
        stmt = stmt.where(ScanRecord.source == source)

    total_query = select(func.count(ScanRecord.id))
    if verdict:
        total_query = total_query.where(ScanRecord.verdict == verdict)
    if source:
        total_query = total_query.where(ScanRecord.source == source)

    total = (await db.execute(total_query)).scalar() or 0
    records = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": str(r.id),
                "sha256": r.sha256,
                "url": r.url,
                "target": r.target,
                "source": r.source,
                "verdict": r.verdict,
                "findings": r.findings,
                "scanned_bytes": r.scanned_bytes,
                "from_cache": r.from_cache,
                "user_id": str(r.user_id) if r.user_id else None,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


@router.get("/stats")
async def get_scan_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate threat scan platform statistics."""
    check_admin(current_user)

    verdicts_stmt = select(ScanRecord.verdict, func.count(ScanRecord.id)).group_by(
        ScanRecord.verdict
    )
    verdict_rows = (await db.execute(verdicts_stmt)).all()
    verdict_counts = {row[0]: row[1] for row in verdict_rows}

    sources_stmt = select(ScanRecord.source, func.count(ScanRecord.id)).group_by(ScanRecord.source)
    source_rows = (await db.execute(sources_stmt)).all()
    source_counts = {row[0]: row[1] for row in source_rows}

    total_scans = (await db.execute(select(func.count(ScanRecord.id)))).scalar() or 0
    cache_hits = (
        await db.execute(select(func.count(ScanRecord.id)).where(ScanRecord.from_cache == True))  # noqa: E712
    ).scalar() or 0
    total_bytes = (
        await db.execute(select(func.coalesce(func.sum(ScanRecord.scanned_bytes), 0)))
    ).scalar() or 0

    return {
        "total_scans": total_scans,
        "cache_hits": cache_hits,
        "cache_hit_rate": round((cache_hits / total_scans) if total_scans > 0 else 0.0, 3),
        "total_bytes_scanned": total_bytes,
        "verdict_breakdown": verdict_counts,
        "source_breakdown": source_counts,
    }


@router.get("/config")
async def get_scanner_config(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect threat scanner configuration status and layer availability."""
    check_admin(current_user)

    return {
        "security_scan_enabled": settings.SECURITY_SCAN_ENABLED,
        "block_threshold": settings.SECURITY_SCAN_BLOCK_THRESHOLD,
        "fail_unavailable_mode": settings.SECURITY_SCAN_FAIL_UNAVAILABLE_MODE,
        "scan_sources": settings.SECURITY_SCAN_SOURCES or "*",
        "archive_limits": {
            "max_entries": settings.ARCHIVE_MAX_ENTRIES,
            "max_uncompressed_bytes": settings.ARCHIVE_MAX_UNCOMPRESSED_BYTES,
            "max_ratio": settings.ARCHIVE_MAX_RATIO,
            "max_nested_depth": settings.ARCHIVE_MAX_NESTED_DEPTH,
        },
        "layers": {
            "layer_0_local_rules": {
                "configured": True,
                "live": True,
            },
            "layer_1_clamav": {
                "configured": settings.CLAMAV_ENABLED,
                "live": _clamav_probe.available(),
                "host": settings.CLAMAV_HOST,
                "port": settings.CLAMAV_PORT,
            },
            "layer_2_virustotal": {
                "configured": settings.VIRUSTOTAL_ENABLED,
                "acknowledged_tos": settings.VIRUSTOTAL_ACK_TOS,
                "live": _vt_probe.available(),
                "api_key_configured": bool(settings.VIRUSTOTAL_API_KEY.strip()),
                "api_key_masked": mask_secret(settings.VIRUSTOTAL_API_KEY)
                if settings.VIRUSTOTAL_API_KEY
                else "",
                "rpm_limit": settings.VIRUSTOTAL_RPM,
                "daily_limit": settings.VIRUSTOTAL_DAILY,
            },
        },
    }


@router.post("/scan/file")
async def admin_scan_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """On-demand scan of an uploaded file by an administrator without blocking."""
    check_admin(current_user)

    filename = file.filename or "unknown.bin"
    max_bytes = 50 * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large for on-demand scan (max 50MB)")

    result = await scan_file(contents, filename=filename, source="admin.manual_scan")

    return {
        "filename": filename,
        "sha256": result.sha256,
        "verdict": result.verdict.value,
        "scanned_bytes": result.scanned_bytes,
        "duration_ms": result.duration_ms,
        "from_cache": result.from_cache,
        "findings": [
            {
                "source": f.source,
                "verdict": f.verdict.value,
                "reason": f.reason,
                "detail": f.detail,
            }
            for f in result.findings
        ],
    }
