"""
AI Solution Builder — Layer 0: Local Security Rules Scanner
(Phase 3 of Threat Scanning Implementation Plan SEC-SCAN-001)

Synchronous, offline, sub-millisecond inspection carrying production security.
Zero third-party pip dependencies.
"""

from __future__ import annotations

import io
import math
import time
import zipfile
from urllib.parse import urlparse

from app.services.security.archive import guard_archive
from app.services.security.types import (
    ArchiveRejectedError,
    ScanFinding,
    ScanResult,
    ScanVerdict,
    worst_verdict,
)

# EICAR standard antivirus test signature
EICAR_CANARY = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"

# Dangerous executable file extensions
DENYLISTED_EXTENSIONS = {
    ".exe",
    ".dll",
    ".scr",
    ".com",
    ".pif",
    ".bat",
    ".cmd",
    ".ps1",
    ".psm1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".ws",
    ".hta",
    ".msi",
    ".msp",
    ".jar",
    ".apk",
    ".lnk",
    ".reg",
    ".sh",
    ".bash",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".iso",
    ".img",
    ".vhd",
    ".cpl",
    ".chm",
    ".gadget",
}

# Macro-enabled Microsoft Office extensions
MACRO_EXTENSIONS = {
    ".xlsm",
    ".docm",
    ".dotm",
    ".pptm",
    ".xltm",
    ".potm",
    ".ppam",
}

# Safe user document & media extensions supported by AI Solution Builder
SAFE_INGEST_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".csv",
    ".xlsx",
    ".xls",
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".webm",
    ".flac",
    ".zip",
}

# Executable binary magic signatures: (offset, byte_pattern, label)
EXEC_MAGIC_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"MZ", "windows_pe"),
    (0, b"\x7fELF", "linux_elf"),
    (0, b"\xfe\xed\xfa\xce", "macho_32"),
    (0, b"\xfe\xed\xfa\xcf", "macho_64"),
    (0, b"\xce\xfa\xed\xfe", "macho_32_rev"),
    (0, b"\xcf\xfa\xed\xfe", "macho_64_rev"),
    (0, b"\xca\xfe\xba\xbe", "mach_fat_binary"),
    (0, b"dex\n", "android_dex"),
    (0, b"\x00asm", "wasm_binary"),
)

# OLE2 Compound Document Header (legacy .doc, .xls, .ppt)
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Known OOXML VBA macro files
OOXML_MACRO_ENTRIES = {
    "word/vbaproject.bin",
    "xl/vbaproject.bin",
    "ppt/vbaproject.bin",
    "vbaproject.bin",
}


def _shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy (bits per byte, 0.0 to 8.0)."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    for count in counts:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


class LocalRulesScanner:
    """Layer 0 threat scanner applying deterministic offline rules."""

    name: str = "local_rules"

    def available(self) -> bool:
        """Local rules are always offline and unconditionally available."""
        return True

    async def scan_bytes(self, data: bytes, *, filename: str) -> ScanResult:
        start_time = time.perf_counter()
        findings: list[ScanFinding] = []
        name_lower = filename.lower()
        ext = "." + name_lower.rsplit(".", 1)[-1] if "." in name_lower else ""

        # 1. EICAR Canary Test String
        if EICAR_CANARY in data:
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="eicar_test_file",
                    detail={"match": "EICAR-STANDARD-ANTIVIRUS-TEST-FILE"},
                )
            )

        # 2. Denylisted extension
        if ext in DENYLISTED_EXTENSIONS:
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="denylisted_extension",
                    detail={"extension": ext, "filename": filename},
                )
            )

        # 3. Macro-enabled Office extensions
        if ext in MACRO_EXTENSIONS:
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="macro_enabled_office",
                    detail={"extension": ext, "filename": filename},
                )
            )

        # 4. Executable magic inspection
        is_exec = False
        exec_label = ""
        for offset, signature, label in EXEC_MAGIC_SIGNATURES:
            sig_len = len(signature)
            if len(data) >= offset + sig_len and data[offset : offset + sig_len] == signature:
                # Disambiguate Java class file from Mach-O fat binary if needed
                is_exec = True
                exec_label = label
                break

        if is_exec:
            # Polyglot / extension spoofing: executable magic disguised with a safe document/media extension
            if ext in SAFE_INGEST_EXTENSIONS:
                findings.append(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.SUSPICIOUS,
                        reason="exec_magic_mismatch",
                        detail={
                            "signature": exec_label,
                            "extension": ext,
                            "filename": filename,
                        },
                    )
                )
            else:
                findings.append(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.MALICIOUS,
                        reason="exec_magic",
                        detail={"signature": exec_label, "filename": filename},
                    )
                )

        # 5. OLE2 Compound File Magic (legacy macro carriers)
        if len(data) >= 8 and data[:8] == OLE2_MAGIC:
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.SUSPICIOUS,
                    reason="ole2_compound",
                    detail={"filename": filename},
                )
            )

        # 6. OOXML Macro inspection (VBA bin within PK zip structure)
        if len(data) >= 4 and data[:4] == b"PK\x03\x04":
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for member in zf.infolist():
                        if member.filename.lower() in OOXML_MACRO_ENTRIES:
                            findings.append(
                                ScanFinding(
                                    source=self.name,
                                    verdict=ScanVerdict.MALICIOUS,
                                    reason="ooxml_macro",
                                    detail={
                                        "macro_entry": member.filename,
                                        "filename": filename,
                                    },
                                )
                            )
                            break
            except Exception:
                pass

        # 7. Magic <-> Extension mismatch (e.g. %PDF- named .jpg, or ZIP magic named .pdf)
        if ext in (".jpg", ".jpeg", ".png", ".webp") and data.startswith(b"%PDF-"):
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.SUSPICIOUS,
                    reason="magic_mismatch",
                    detail={"magic": "pdf", "extension": ext, "filename": filename},
                )
            )
        elif ext == ".pdf" and data.startswith(b"PK\x03\x04"):
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.SUSPICIOUS,
                    reason="magic_mismatch",
                    detail={"magic": "zip", "extension": ext, "filename": filename},
                )
            )

        # 8. High entropy blob masked as text/document
        if ext in (".txt", ".md", ".csv", ".json", ".yaml", ".yml") and len(data) > 1024:
            entropy = _shannon_entropy(data[:16384])
            if entropy > 7.5:
                findings.append(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.SUSPICIOUS,
                        reason="high_entropy_blob",
                        detail={
                            "entropy": round(entropy, 2),
                            "extension": ext,
                            "filename": filename,
                        },
                    )
                )

        # 9. Archive structure inspection (if file is a zip or zip magic)
        if ext == ".zip" or (len(data) >= 4 and data[:4] == b"PK\x03\x04"):
            try:
                guard_archive(data, source="local_rules")
            except ArchiveRejectedError as are:
                for f in are.findings:
                    findings.append(f)

        duration = (time.perf_counter() - start_time) * 1000
        verdict = worst_verdict(findings)

        return ScanResult(
            verdict=verdict,
            findings=tuple(findings),
            scanned_bytes=len(data),
            duration_ms=round(duration, 2),
            from_cache=False,
        )

    async def scan_url(self, url: str) -> ScanResult:
        start_time = time.perf_counter()
        findings: list[ScanFinding] = []

        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            if scheme not in ("http", "https"):
                findings.append(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.MALICIOUS,
                        reason="forbidden_url_scheme",
                        detail={"scheme": scheme, "url": url},
                    )
                )

            # Embedded credentials in URL (e.g. https://user:pass@evil.com)
            if parsed.username or parsed.password:
                findings.append(
                    ScanFinding(
                        source=self.name,
                        verdict=ScanVerdict.SUSPICIOUS,
                        reason="url_embedded_credentials",
                        detail={"url": url},
                    )
                )
        except Exception as exc:
            findings.append(
                ScanFinding(
                    source=self.name,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="invalid_url",
                    detail={"error": str(exc), "url": url},
                )
            )

        duration = (time.perf_counter() - start_time) * 1000
        verdict = worst_verdict(findings)

        return ScanResult(
            verdict=verdict,
            findings=tuple(findings),
            url=url,
            duration_ms=round(duration, 2),
            from_cache=False,
        )
