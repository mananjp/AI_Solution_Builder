"""
AI Solution Builder — Scanner Protocol
(Phase 1.2 of Threat Scanning Implementation Plan SEC-SCAN-001)

Structural subtyping protocol for all threat scanning layers.
"""

from __future__ import annotations

from typing import Protocol

from app.services.security.types import ScanResult


class Scanner(Protocol):
    """Protocol for scanning engines (local rules, ClamAV, VirusTotal)."""

    name: str

    def available(self) -> bool:
        """Check whether the scanner is configured, healthy, and available."""
        ...

    async def scan_bytes(self, data: bytes, *, filename: str) -> ScanResult:
        """Scan raw binary file contents."""
        ...

    async def scan_url(self, url: str) -> ScanResult:
        """Scan a URL or domain target."""
        ...
