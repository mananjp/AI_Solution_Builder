"""
AI Solution Builder — Layer 2: VirusTotal API Scanner (Opt-In)
(Phase 5 of Threat Scanning Implementation Plan SEC-SCAN-001)

Integration with VirusTotal v3 REST API.
Gated on VIRUSTOTAL_ACK_TOS and rate-limited to 4 RPM / 500 Daily.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from typing import Any, cast

import httpx

from app.core.config import settings
from app.services.security.ratelimit import acquire_virustotal_quota
from app.services.security.types import (
    ScanFinding,
    ScanResult,
    ScanVerdict,
)

logger = logging.getLogger(__name__)

VIRUSTOTAL_API_BASE = "https://www.virustotal.com/api/v3"

# Allowlisted fields extracted from VT response to comply with redistribution terms
VT_FILE_DETAIL_FIELDS = (
    "last_analysis_stats",
    "last_analysis_date",
    "sha256",
    "size",
    "type_description",
    "meaningful_name",
    "reputation",
)

VT_URL_DETAIL_FIELDS = (
    "last_analysis_stats",
    "last_analysis_date",
    "url",
    "reputation",
    "threat_names",
    "categories",
)


class VirusTotalError(RuntimeError):
    """Raised when a VirusTotal API error occurs."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def virustotal_configured(*, api_key: str | None = None) -> bool:
    """Check if VirusTotal layer is properly configured and ToS acknowledged."""
    key = api_key if api_key is not None else settings.VIRUSTOTAL_API_KEY
    return bool(settings.VIRUSTOTAL_ENABLED and settings.VIRUSTOTAL_ACK_TOS and key and key.strip())


def url_identifier(url: str) -> str:
    """Compute VirusTotal unpadded URLsafe Base64 identifier (RFC 4648 §3.2)."""
    return base64.urlsafe_b64encode(url.strip().encode("utf-8")).decode("ascii").rstrip("=")


def _extract_allowlisted_details(
    attrs: dict[str, Any], allowed_keys: tuple[str, ...]
) -> dict[str, Any]:
    """Filter attributes dictionary to allowlisted fields only."""
    return {k: attrs[k] for k in allowed_keys if k in attrs}


def _verdict_from_stats(stats: dict[str, int]) -> tuple[ScanVerdict, str]:
    """Compute scan verdict and reason code from VT last_analysis_stats."""
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)

    if malicious >= settings.VIRUSTOTAL_MIN_DETECTIONS:
        return ScanVerdict.MALICIOUS, "virustotal_detection"
    elif malicious >= 1 or suspicious >= 2:
        return ScanVerdict.SUSPICIOUS, "virustotal_suspicious"
    else:
        return ScanVerdict.CLEAN, "virustotal_clean"


async def lookup_file(sha256: str, api_key: str | None = None) -> ScanResult:
    """Query VirusTotal v3 for an existing file report by SHA-256 hash."""
    key = api_key or settings.VIRUSTOTAL_API_KEY
    headers = {"x-apikey": key, "Accept": "application/json"}
    url = f"{VIRUSTOTAL_API_BASE}/files/{sha256}"

    start_time = time.perf_counter()
    async with httpx.AsyncClient(timeout=settings.VIRUSTOTAL_TIMEOUT) as client:
        try:
            resp = await client.get(url, headers=headers)
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning("VirusTotal lookup request error: %s", exc)
            return ScanResult(
                verdict=ScanVerdict.ERROR,
                findings=(
                    ScanFinding(
                        source="virustotal",
                        verdict=ScanVerdict.ERROR,
                        reason="virustotal_network_error",
                        detail={"error": str(exc)},
                    ),
                ),
                sha256=sha256,
                duration_ms=round(duration, 2),
            )

    duration = (time.perf_counter() - start_time) * 1000

    if resp.status_code == 404:
        # File has not been seen by VirusTotal — this is UNKNOWN, never an error
        return ScanResult(
            verdict=ScanVerdict.UNKNOWN,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.UNKNOWN,
                    reason="virustotal_hash_not_found",
                    detail={"sha256": sha256},
                ),
            ),
            sha256=sha256,
            duration_ms=round(duration, 2),
        )
    elif resp.status_code == 429:
        logger.warning("VirusTotal API quota exceeded (HTTP 429)")
        return ScanResult(
            verdict=ScanVerdict.ERROR,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.ERROR,
                    reason="virustotal_quota_exceeded",
                    detail={"status_code": 429},
                ),
            ),
            sha256=sha256,
            duration_ms=round(duration, 2),
        )
    elif resp.status_code != 200:
        logger.warning(
            "VirusTotal file query returned HTTP %d: %s", resp.status_code, resp.text[:100]
        )
        return ScanResult(
            verdict=ScanVerdict.ERROR,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.ERROR,
                    reason="virustotal_api_error",
                    detail={"status_code": resp.status_code},
                ),
            ),
            sha256=sha256,
            duration_ms=round(duration, 2),
        )

    body = cast(dict[str, Any], resp.json())
    attrs = body.get("data", {}).get("attributes", {})
    stats = cast(dict[str, int], attrs.get("last_analysis_stats", {}))

    verdict, reason = _verdict_from_stats(stats)
    detail = _extract_allowlisted_details(attrs, VT_FILE_DETAIL_FIELDS)

    return ScanResult(
        verdict=verdict,
        findings=(
            ScanFinding(
                source="virustotal",
                verdict=verdict,
                reason=reason,
                detail=detail,
            ),
        ),
        sha256=sha256,
        scanned_bytes=attrs.get("size", 0),
        duration_ms=round(duration, 2),
    )


async def lookup_url(target_url: str, api_key: str | None = None) -> ScanResult:
    """Query VirusTotal v3 for an existing URL report by base64 identifier."""
    key = api_key or settings.VIRUSTOTAL_API_KEY
    url_id = url_identifier(target_url)
    headers = {"x-apikey": key, "Accept": "application/json"}
    endpoint = f"{VIRUSTOTAL_API_BASE}/urls/{url_id}"

    start_time = time.perf_counter()
    async with httpx.AsyncClient(timeout=settings.VIRUSTOTAL_TIMEOUT) as client:
        try:
            resp = await client.get(endpoint, headers=headers)
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning("VirusTotal URL query request error: %s", exc)
            return ScanResult(
                verdict=ScanVerdict.ERROR,
                findings=(
                    ScanFinding(
                        source="virustotal",
                        verdict=ScanVerdict.ERROR,
                        reason="virustotal_network_error",
                        detail={"error": str(exc)},
                    ),
                ),
                url=target_url,
                duration_ms=round(duration, 2),
            )

    duration = (time.perf_counter() - start_time) * 1000

    if resp.status_code == 404:
        return ScanResult(
            verdict=ScanVerdict.UNKNOWN,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.UNKNOWN,
                    reason="virustotal_url_not_found",
                    detail={"url": target_url},
                ),
            ),
            url=target_url,
            duration_ms=round(duration, 2),
        )
    elif resp.status_code == 429:
        logger.warning("VirusTotal API quota exceeded on URL lookup")
        return ScanResult(
            verdict=ScanVerdict.ERROR,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.ERROR,
                    reason="virustotal_quota_exceeded",
                    detail={"status_code": 429},
                ),
            ),
            url=target_url,
            duration_ms=round(duration, 2),
        )
    elif resp.status_code != 200:
        return ScanResult(
            verdict=ScanVerdict.ERROR,
            findings=(
                ScanFinding(
                    source="virustotal",
                    verdict=ScanVerdict.ERROR,
                    reason="virustotal_api_error",
                    detail={"status_code": resp.status_code},
                ),
            ),
            url=target_url,
            duration_ms=round(duration, 2),
        )

    body = cast(dict[str, Any], resp.json())
    attrs = body.get("data", {}).get("attributes", {})
    stats = cast(dict[str, int], attrs.get("last_analysis_stats", {}))

    verdict, reason = _verdict_from_stats(stats)
    detail = _extract_allowlisted_details(attrs, VT_URL_DETAIL_FIELDS)

    return ScanResult(
        verdict=verdict,
        findings=(
            ScanFinding(
                source="virustotal",
                verdict=verdict,
                reason=reason,
                detail=detail,
            ),
        ),
        url=target_url,
        duration_ms=round(duration, 2),
    )


async def upload_file(data: bytes, filename: str, api_key: str | None = None) -> str:
    """Submit a file to VirusTotal for analysis. Returns analysis ID.

    Refuses uploads exceeding VIRUSTOTAL_MAX_UPLOAD_BYTES (32 MB cap).
    """
    if len(data) > settings.VIRUSTOTAL_MAX_UPLOAD_BYTES:
        raise VirusTotalError(
            f"File size ({len(data)} bytes) exceeds VirusTotal 32MB upload ceiling "
            f"({settings.VIRUSTOTAL_MAX_UPLOAD_BYTES} bytes)"
        )

    key = api_key or settings.VIRUSTOTAL_API_KEY
    headers = {"x-apikey": key}
    url = f"{VIRUSTOTAL_API_BASE}/files"

    files = {"file": (filename, data)}
    async with httpx.AsyncClient(timeout=settings.VIRUSTOTAL_UPLOAD_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, files=files)
        if resp.status_code != 200:
            raise VirusTotalError(
                f"VirusTotal file upload failed ({resp.status_code}): {resp.text[:120]}",
                status_code=resp.status_code,
            )
        body = cast(dict[str, Any], resp.json())
        return str(body.get("data", {}).get("id", ""))


async def poll_analysis(analysis_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Check the status of a pending VirusTotal analysis."""
    key = api_key or settings.VIRUSTOTAL_API_KEY
    headers = {"x-apikey": key, "Accept": "application/json"}
    url = f"{VIRUSTOTAL_API_BASE}/analyses/{analysis_id}"

    async with httpx.AsyncClient(timeout=settings.VIRUSTOTAL_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise VirusTotalError(
                f"Poll analysis failed ({resp.status_code})", status_code=resp.status_code
            )
        body = cast(dict[str, Any], resp.json())
        return cast(dict[str, Any], body.get("data", {}).get("attributes", {}))


async def submit_url(target_url: str, api_key: str | None = None) -> str:
    """Submit a URL to VirusTotal for scanning. Returns analysis ID."""
    key = api_key or settings.VIRUSTOTAL_API_KEY
    headers = {"x-apikey": key}
    url = f"{VIRUSTOTAL_API_BASE}/urls"

    async with httpx.AsyncClient(timeout=settings.VIRUSTOTAL_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, data={"url": target_url})
        if resp.status_code != 200:
            raise VirusTotalError(
                f"VirusTotal URL submit failed ({resp.status_code}): {resp.text[:120]}",
                status_code=resp.status_code,
            )
        body = cast(dict[str, Any], resp.json())
        return str(body.get("data", {}).get("id", ""))


class VirusTotalScanner:
    """Layer 2 threat scanner calling VirusTotal v3 REST API."""

    name: str = "virustotal"

    def available(self) -> bool:
        """VirusTotal is available only when enabled, ToS acknowledged, and key set."""
        return virustotal_configured()

    async def scan_bytes(self, data: bytes, *, filename: str) -> ScanResult:
        if not self.available():
            return ScanResult(verdict=ScanVerdict.SKIPPED)

        quota_ok = await acquire_virustotal_quota()
        if not quota_ok:
            return ScanResult(
                verdict=ScanVerdict.SKIPPED,
                findings=(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.SKIPPED,
                        reason="virustotal_rate_limited",
                        detail={"filename": filename},
                    ),
                ),
            )

        sha256 = hashlib.sha256(data).hexdigest()
        return await lookup_file(sha256)

    async def scan_url(self, url: str) -> ScanResult:
        if not self.available():
            return ScanResult(verdict=ScanVerdict.SKIPPED, url=url)

        quota_ok = await acquire_virustotal_quota()
        if not quota_ok:
            return ScanResult(
                verdict=ScanVerdict.SKIPPED,
                findings=(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.SKIPPED,
                        reason="virustotal_rate_limited",
                        detail={"url": url},
                    ),
                ),
                url=url,
            )

        return await lookup_url(url)
