"""
AI Solution Builder — Security Verdict Cache
(Phase 5 of Threat Scanning Implementation Plan SEC-SCAN-001)

Redis-backed verdict caching for clean and malicious targets.
Caches on sha256 and base64 url identifier for 7 days to preserve VT quota.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.redis import redis_get_json, redis_set_json
from app.services.security.types import ScanFinding, ScanResult, ScanVerdict

logger = logging.getLogger(__name__)


def _serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    return {
        "verdict": result.verdict.value,
        "sha256": result.sha256,
        "url": result.url,
        "scanned_bytes": result.scanned_bytes,
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


def _deserialize_scan_result(data: dict[str, Any]) -> ScanResult:
    findings = tuple(
        ScanFinding(
            source=f["source"],
            verdict=ScanVerdict(f["verdict"]),
            reason=f["reason"],
            detail=f.get("detail", {}),
        )
        for f in data.get("findings", [])
    )
    return ScanResult(
        verdict=ScanVerdict(data["verdict"]),
        findings=findings,
        sha256=data.get("sha256"),
        url=data.get("url"),
        scanned_bytes=int(data.get("scanned_bytes", 0)),
        duration_ms=0.0,
        from_cache=True,
    )


async def get_cached_scan(target_type: str, key_id: str) -> ScanResult | None:
    """Fetch cached verdict by key (sha256 or url_id)."""
    cache_key = f"scan:{target_type}:{key_id}"
    try:
        data = await redis_get_json(cache_key)
        if data:
            return _deserialize_scan_result(data)
    except Exception as exc:
        logger.debug("Scan cache read failed: %s", exc)
    return None


async def set_cached_scan(
    target_type: str,
    key_id: str,
    result: ScanResult,
    ttl_seconds: int | None = None,
) -> None:
    """Persist verdict in Redis cache for the configured TTL."""
    cache_key = f"scan:{target_type}:{key_id}"
    ttl = ttl_seconds or settings.SECURITY_CACHE_TTL
    try:
        payload = _serialize_scan_result(result)
        await redis_set_json(cache_key, payload, ttl_seconds=ttl)
    except Exception as exc:
        logger.debug("Scan cache write failed: %s", exc)
