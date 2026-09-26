"""
AI Solution Builder — Security Scanning Orchestrator
(Phase 6 of Threat Scanning Implementation Plan SEC-SCAN-001)

Single unified entry point for all route guards and threat scanning layers.
Fans out across Layer 0 (Local), Layer 1 (ClamAV), Layer 2 (VirusTotal).
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import logging
import re
import time

from fastapi import HTTPException

from app.core.config import settings
from app.services.security.archive import guard_archive as _raw_guard_archive
from app.services.security.base import Scanner
from app.services.security.cache import get_cached_scan, set_cached_scan
from app.services.security.clamav import ClamAVScanner
from app.services.security.local_rules import LocalRulesScanner
from app.services.security.types import (
    ArchiveRejectedError,
    ScanFinding,
    ScanResult,
    ScanVerdict,
    worst_verdict,
)
from app.services.security.virustotal import VirusTotalScanner, url_identifier

logger = logging.getLogger(__name__)

# URL regex for extracting links from generated text / templates
_URL_REGEX = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

# Instantiate scanning layers
_LOCAL_SCANNER = LocalRulesScanner()
_CLAMAV_SCANNER = ClamAVScanner()
_VT_SCANNER = VirusTotalScanner()

_ALL_SCANNERS: tuple[Scanner, ...] = (_LOCAL_SCANNER, _CLAMAV_SCANNER, _VT_SCANNER)


def is_source_enabled(source: str) -> bool:
    """Check if the given source matches SECURITY_SCAN_SOURCES glob allowlist."""
    if not settings.SECURITY_SCAN_ENABLED:
        return False
    allowed_patterns = settings.SECURITY_SCAN_SOURCES.strip()
    if not allowed_patterns:
        return True
    patterns = [p.strip() for p in allowed_patterns.split(",") if p.strip()]
    return any(fnmatch.fnmatch(source, pat) for pat in patterns)


def guard_archive(zip_bytes: bytes, *, source: str = "archive") -> None:
    """Inspect and validate archive central directory before decompression.

    Raises HTTPException(422, code=SECURITY_ARCHIVE_REJECTED) on zip bomb or path traversal.
    """
    try:
        _raw_guard_archive(zip_bytes, source=source)
    except ArchiveRejectedError as are:
        logger.warning("Archive rejected for source %s: %s", source, are.message)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SECURITY_ARCHIVE_REJECTED",
                "message": are.message,
                "details": [f.reason for f in are.findings],
            },
        ) from are


async def scan_file(data: bytes, *, filename: str, source: str) -> ScanResult:
    """Scan raw binary file contents across all available scanning layers."""
    start_time = time.perf_counter()

    if not is_source_enabled(source):
        return ScanResult(verdict=ScanVerdict.SKIPPED, scanned_bytes=len(data))

    sha256 = hashlib.sha256(data).hexdigest()

    # 1. Check Redis cache first
    cached = await get_cached_scan("file", sha256)
    if cached is not None:
        return cached

    # 2. Collect available scanners
    active_scanners = [s for s in _ALL_SCANNERS if s.available()]
    if not active_scanners:
        return ScanResult(
            verdict=ScanVerdict.UNKNOWN,
            findings=(
                ScanFinding(
                    source="orchestrator",
                    verdict=ScanVerdict.ERROR,
                    reason="no_scanners_available",
                ),
            ),
            sha256=sha256,
            scanned_bytes=len(data),
        )

    # 3. Fan-out execution concurrently
    tasks = [scanner.scan_bytes(data, filename=filename) for scanner in active_scanners]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_findings: list[ScanFinding] = []
    has_success = False

    for scanner, res in zip(active_scanners, results, strict=False):
        if isinstance(res, Exception):
            logger.warning("Scanner %s raised exception on file %s: %s", scanner.name, filename, res)
            all_findings.append(
                ScanFinding(
                    source=scanner.name,
                    verdict=ScanVerdict.ERROR,
                    reason=f"{scanner.name}_exception",
                    detail={"error": str(res)},
                )
            )
        elif isinstance(res, ScanResult):
            has_success = True
            all_findings.extend(res.findings)

    # 4. Aggregate verdict
    final_verdict = worst_verdict(all_findings)
    duration = (time.perf_counter() - start_time) * 1000

    scan_result = ScanResult(
        verdict=final_verdict,
        findings=tuple(all_findings),
        sha256=sha256,
        scanned_bytes=len(data),
        duration_ms=round(duration, 2),
        from_cache=False,
    )

    # 5. Persist verdict in Redis cache
    if has_success:
        await set_cached_scan("file", sha256, scan_result)

    return scan_result


async def scan_url(url: str, *, source: str) -> ScanResult:
    """Scan a target URL across available reputation engines."""
    start_time = time.perf_counter()

    if not is_source_enabled(source):
        return ScanResult(verdict=ScanVerdict.SKIPPED, url=url)

    url_id = url_identifier(url)

    # 1. Check Redis cache
    cached = await get_cached_scan("url", url_id)
    if cached is not None:
        return cached

    # 2. Collect available scanners for URL scanning
    active_scanners = [s for s in _ALL_SCANNERS if s.available()]
    if not active_scanners:
        return ScanResult(
            verdict=ScanVerdict.UNKNOWN,
            findings=(
                ScanFinding(
                    source="orchestrator",
                    verdict=ScanVerdict.ERROR,
                    reason="no_scanners_available",
                ),
            ),
            url=url,
        )

    # 3. Fan-out execution concurrently
    tasks = [scanner.scan_url(url) for scanner in active_scanners]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_findings: list[ScanFinding] = []
    has_success = False

    for scanner, res in zip(active_scanners, results, strict=False):
        if isinstance(res, Exception):
            logger.warning("Scanner %s raised exception on URL %s: %s", scanner.name, url, res)
            all_findings.append(
                ScanFinding(
                    source=scanner.name,
                    verdict=ScanVerdict.ERROR,
                    reason=f"{scanner.name}_exception",
                    detail={"error": str(res)},
                )
            )
        elif isinstance(res, ScanResult):
            has_success = True
            all_findings.extend(res.findings)

    # 4. Aggregate verdict
    final_verdict = worst_verdict(all_findings)
    duration = (time.perf_counter() - start_time) * 1000

    scan_result = ScanResult(
        verdict=final_verdict,
        findings=tuple(all_findings),
        url=url,
        duration_ms=round(duration, 2),
        from_cache=False,
    )

    # 5. Persist verdict in Redis cache
    if has_success:
        await set_cached_scan("url", url_id, scan_result)

    return scan_result


def enforce(result: ScanResult, *, source: str) -> None:
    """Apply configured enforcement policy against a scan result.

    Raises:
    - HTTPException(422, code=SECURITY_SCAN_BLOCKED) if threshold reached
    - HTTPException(403, code=SECURITY_QUARANTINED) if unavailable and fail_mode=quarantine
    - HTTPException(503, code=SCANNER_UNAVAILABLE) if unavailable and fail_mode=block
    """
    if result.verdict == ScanVerdict.SKIPPED:
        return

    # Check for detection exceeding block threshold
    block_threshold = settings.SECURITY_SCAN_BLOCK_THRESHOLD.lower()
    should_block = False

    if block_threshold == "suspicious":
        should_block = result.verdict in (ScanVerdict.MALICIOUS, ScanVerdict.SUSPICIOUS)
    elif block_threshold == "malicious":
        should_block = result.verdict == ScanVerdict.MALICIOUS

    if should_block:
        reasons = [
            f.reason
            for f in result.findings
            if f.verdict in (ScanVerdict.MALICIOUS, ScanVerdict.SUSPICIOUS)
        ]
        logger.warning(
            "Threat scan blocked asset from %s (verdict=%s, reasons=%s)",
            source,
            result.verdict.value,
            reasons,
        )
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SECURITY_SCAN_BLOCKED",
                "message": f"Asset blocked by threat scanner: detected as {result.verdict.value}",
                "details": reasons,
            },
        )

    # Handle total scanner failure / unavailability
    has_error = any(f.verdict == ScanVerdict.ERROR for f in result.findings)
    has_non_error = any(
        f.verdict in (ScanVerdict.CLEAN, ScanVerdict.MALICIOUS, ScanVerdict.SUSPICIOUS, ScanVerdict.UNKNOWN)
        for f in result.findings
    )

    if has_error and not has_non_error:
        fail_mode = settings.SECURITY_SCAN_FAIL_UNAVAILABLE_MODE.lower()
        if fail_mode == "quarantine":
            logger.error("Scanners unavailable and fail_mode=quarantine for source %s", source)
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SECURITY_QUARANTINED",
                    "message": "Threat scanners unavailable; request quarantined per security policy",
                    "details": [],
                },
            )
        elif fail_mode == "block":
            logger.error("Scanners unavailable and fail_mode=block for source %s", source)
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "SCANNER_UNAVAILABLE",
                    "message": "Threat scanners unavailable; request rejected per security policy",
                    "details": [],
                },
            )
        else:
            logger.warning("Scanners unavailable, fail_mode=allow; permitting source %s", source)


async def enforce_file(data: bytes, filename: str, *, source: str) -> ScanResult:
    """Convenience helper: scan bytes and enforce policy immediately."""
    result = await scan_file(data, filename=filename, source=source)
    enforce(result, source=source)
    return result


async def enforce_url(url: str, *, source: str) -> ScanResult:
    """Convenience helper: scan URL and enforce policy immediately."""
    result = await scan_url(url, source=source)
    enforce(result, source=source)
    return result


async def enforce_urls_in_text(text: str, *, source: str) -> list[ScanResult]:
    """Scan and enforce all URLs embedded within generated text or code."""
    if not settings.SCAN_GENERATED_ARTIFACTS:
        return []

    urls = _URL_REGEX.findall(text)
    results: list[ScanResult] = []
    for target_url in set(urls):
        res = await enforce_url(target_url, source=f"{source}:url")
        results.append(res)
    return results
