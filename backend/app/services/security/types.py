"""
AI Solution Builder — Security Scanning Types & Data Structures
(Phase 1.1 of Threat Scanning Implementation Plan SEC-SCAN-001)

Core vocabulary shared by all scanning layers. mypy --strict compliant.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ScanVerdict(StrEnum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"
    ERROR = "error"
    SKIPPED = "skipped"


class ScanTarget(StrEnum):
    FILE = "file"
    URL = "url"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class ScanFinding:
    source: str  # "local_rules" | "clamav" | "virustotal" | "archive"
    verdict: ScanVerdict
    reason: str  # stable machine code, e.g. "exec_magic_mismatch"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanResult:
    verdict: ScanVerdict
    findings: tuple[ScanFinding, ...] = ()
    sha256: str | None = None
    url: str | None = None
    scanned_bytes: int = 0
    duration_ms: float = 0.0
    from_cache: bool = False


# Severity ranking for findings aggregation:
# MALICIOUS > SUSPICIOUS > UNKNOWN > CLEAN > SKIPPED.
# ERROR is deliberately excluded from escalation (surfaced as finding, not verdict escalation).
_SEVERITY_ORDER: dict[ScanVerdict, int] = {
    ScanVerdict.MALICIOUS: 5,
    ScanVerdict.SUSPICIOUS: 4,
    ScanVerdict.UNKNOWN: 3,
    ScanVerdict.CLEAN: 2,
    ScanVerdict.SKIPPED: 1,
    ScanVerdict.ERROR: 0,
}


def worst_verdict(findings: Sequence[ScanFinding]) -> ScanVerdict:
    """Aggregate findings into the worst non-error verdict.

    Returns ScanVerdict.CLEAN if no non-error findings exist.
    """
    candidates = [f.verdict for f in findings if f.verdict != ScanVerdict.ERROR]
    if not candidates:
        return ScanVerdict.CLEAN
    return max(candidates, key=lambda v: _SEVERITY_ORDER.get(v, 0))


# Alias matching plan notation
_worst = worst_verdict


class ScanBlockedError(Exception):
    """Raised when an asset detection reaches or exceeds the block threshold."""

    def __init__(self, message: str, findings: Sequence[ScanFinding] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.findings = tuple(findings or ())


class ScanQuarantinedError(Exception):
    """Raised when scanning fails/is unavailable and fail_mode is 'quarantine'."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ScannerUnavailableError(Exception):
    """Raised when scanning fails/is unavailable and fail_mode is 'block'."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArchiveRejectedError(ScanBlockedError):
    """Raised when an archive fails structure/safety checks (bomb, slip, nesting)."""
