"""
AI Solution Builder — Security & Threat Scanning Package
(SEC-SCAN-001)

Public entry points and types for route integration and admin endpoints.
"""

from __future__ import annotations

from app.services.security.archive import guard_archive, safe_extract_zip
from app.services.security.orchestrator import (
    enforce,
    enforce_file,
    enforce_url,
    enforce_urls_in_text,
    scan_file,
    scan_url,
)
from app.services.security.types import (
    ArchiveRejectedError,
    ScanBlockedError,
    ScanFinding,
    ScannerUnavailableError,
    ScanQuarantinedError,
    ScanResult,
    ScanTarget,
    ScanVerdict,
    worst_verdict,
)

__all__ = [
    "ArchiveRejectedError",
    "ScanBlockedError",
    "ScanFinding",
    "ScanQuarantinedError",
    "ScanResult",
    "ScanTarget",
    "ScanVerdict",
    "ScannerUnavailableError",
    "enforce",
    "enforce_file",
    "enforce_url",
    "enforce_urls_in_text",
    "guard_archive",
    "safe_extract_zip",
    "scan_file",
    "scan_url",
    "worst_verdict",
]
