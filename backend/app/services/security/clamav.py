"""
AI Solution Builder — Layer 1: ClamAV Network Scanner
(Phase 4 of Threat Scanning Implementation Plan SEC-SCAN-001)

Communicates with clamd over raw TCP zINSTREAM protocol.
Zero third-party pip dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time

from app.core.config import settings
from app.services.security.types import (
    ScanFinding,
    ScanResult,
    ScanVerdict,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192
MAX_STREAM_BYTES = 32 * 1024 * 1024  # 32 MB standard clamd stream limit


class ClamAVScanner:
    """Layer 1 threat scanner connecting to a clamd daemon via raw TCP."""

    name: str = "clamav"

    def __init__(self) -> None:
        self._last_probe_time: float = 0.0
        self._last_probe_result: bool = False

    def available(self) -> bool:
        """Check whether ClamAV is enabled and reachable via TCP."""
        if not settings.CLAMAV_ENABLED:
            return False

        now = time.monotonic()
        cache_duration = max(5.0, settings.CLAMAV_TIMEOUT * 12)
        if now - self._last_probe_time < cache_duration:
            return self._last_probe_result

        # Short sync probe
        try:
            with socket.create_connection(
                (settings.CLAMAV_HOST, settings.CLAMAV_PORT),
                timeout=min(1.0, settings.CLAMAV_TIMEOUT),
            ):
                self._last_probe_result = True
        except (TimeoutError, OSError):
            self._last_probe_result = False

        self._last_probe_time = now
        return self._last_probe_result

    async def scan_bytes(self, data: bytes, *, filename: str) -> ScanResult:
        start_time = time.perf_counter()

        if not settings.CLAMAV_ENABLED:
            return ScanResult(
                verdict=ScanVerdict.SKIPPED,
                scanned_bytes=0,
                duration_ms=0.0,
            )

        truncated = False
        payload = data
        if len(payload) > MAX_STREAM_BYTES:
            payload = data[:MAX_STREAM_BYTES]
            truncated = True

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT),
                timeout=settings.CLAMAV_TIMEOUT,
            )
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "ClamAV connect failed (%s:%s): %s", settings.CLAMAV_HOST, settings.CLAMAV_PORT, exc
            )
            return ScanResult(
                verdict=ScanVerdict.ERROR,
                findings=(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.ERROR,
                        reason="clamav_unavailable",
                        detail={"error": str(exc)},
                    ),
                ),
                scanned_bytes=0,
                duration_ms=round(duration, 2),
            )

        try:
            # Wire format: b"zINSTREAM\0" + chunks + b"\x00\x00\x00\x00"
            writer.write(b"zINSTREAM\0")

            view = memoryview(payload)
            for offset in range(0, len(view), CHUNK_SIZE):
                chunk = view[offset : offset + CHUNK_SIZE]
                chunk_len = len(chunk).to_bytes(4, byteorder="big")
                writer.write(chunk_len + chunk)
                await writer.drain()

            # End of stream marker
            writer.write(b"\x00\x00\x00\x00")
            await writer.drain()

            # Read response
            response_raw = await asyncio.wait_for(
                reader.readuntil(b"\0"),
                timeout=settings.CLAMAV_TIMEOUT,
            )
            response_text = response_raw.decode("utf-8", errors="replace").strip("\0").strip()

            duration = (time.perf_counter() - start_time) * 1000

            # Parse clamd response: e.g. "stream: OK" or "stream: Eicar-Signature FOUND"
            if "FOUND" in response_text:
                sig_part = response_text.replace("stream:", "").replace("FOUND", "").strip()
                finding = ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="clamav_signature",
                    detail={
                        "signature": sig_part,
                        "raw_response": response_text,
                        "filename": filename,
                        "truncated": truncated,
                    },
                )
                return ScanResult(
                    verdict=ScanVerdict.MALICIOUS,
                    findings=(finding,),
                    scanned_bytes=len(payload),
                    duration_ms=round(duration, 2),
                )
            elif "OK" in response_text:
                return ScanResult(
                    verdict=ScanVerdict.CLEAN,
                    findings=(),
                    scanned_bytes=len(payload),
                    duration_ms=round(duration, 2),
                )
            else:
                return ScanResult(
                    verdict=ScanVerdict.ERROR,
                    findings=(
                        ScanFinding(
                            source=self.name,
                            verdict=ScanVerdict.ERROR,
                            reason="clamav_error_response",
                            detail={"response": response_text},
                        ),
                    ),
                    scanned_bytes=len(payload),
                    duration_ms=round(duration, 2),
                )

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning("ClamAV scan error for %s: %s", filename, exc)
            return ScanResult(
                verdict=ScanVerdict.ERROR,
                findings=(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.ERROR,
                        reason="clamav_scan_error",
                        detail={"error": str(exc)},
                    ),
                ),
                scanned_bytes=0,
                duration_ms=round(duration, 2),
            )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def scan_url(self, url: str) -> ScanResult:
        """ClamAV does not perform URL reputation scanning."""
        return ScanResult(
            verdict=ScanVerdict.SKIPPED,
            url=url,
            scanned_bytes=0,
            duration_ms=0.0,
        )
