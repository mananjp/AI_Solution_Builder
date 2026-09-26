"""
AI Solution Builder — Archive Guard & Safe Extraction
(Phase 2 of Threat Scanning Implementation Plan SEC-SCAN-001)

Hardened archive inspection and zip slip / zip bomb protection.
Synchronous, offline, zero network dependencies.
"""

from __future__ import annotations

import io
import logging
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.services.security.types import ArchiveRejectedError, ScanFinding, ScanVerdict

logger = logging.getLogger(__name__)

# File extensions that represent nested archives
_ARCHIVE_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".iso",
}


def _validate_member_filename(filename: str) -> None:
    """Validate archive member path against traversal, absolute paths, and drive letters."""
    # Check for raw backslashes and drive letters
    if "\\" in filename:
        raise ArchiveRejectedError(
            f"Archive member contains forbidden backslash path separator: {filename!r}",
            findings=[
                ScanFinding(
                    source="archive",
                    verdict=ScanVerdict.MALICIOUS,
                    reason="archive_traversal",
                    detail={"filename": filename},
                )
            ],
        )

    if ":" in filename:
        raise ArchiveRejectedError(
            f"Archive member contains drive letter or illegal colon: {filename!r}",
            findings=[
                ScanFinding(
                    source="archive",
                    verdict=ScanVerdict.MALICIOUS,
                    reason="archive_traversal",
                    detail={"filename": filename},
                )
            ],
        )

    # Check for leading slashes
    if filename.startswith("/") or filename.startswith("\\"):
        raise ArchiveRejectedError(
            f"Archive member contains absolute path: {filename!r}",
            findings=[
                ScanFinding(
                    source="archive",
                    verdict=ScanVerdict.MALICIOUS,
                    reason="archive_traversal",
                    detail={"filename": filename},
                )
            ],
        )

    # PurePosixPath segment inspection
    pure_path = PurePosixPath(filename)
    if pure_path.is_absolute():
        raise ArchiveRejectedError(
            f"Archive member path is absolute: {filename!r}",
            findings=[
                ScanFinding(
                    source="archive",
                    verdict=ScanVerdict.MALICIOUS,
                    reason="archive_traversal",
                    detail={"filename": filename},
                )
            ],
        )

    for part in pure_path.parts:
        if part in ("..", "."):
            raise ArchiveRejectedError(
                f"Archive member contains directory traversal segment: {filename!r}",
                findings=[
                    ScanFinding(
                        source="archive",
                        verdict=ScanVerdict.MALICIOUS,
                        reason="archive_traversal",
                        detail={"filename": filename, "part": part},
                    )
                ],
            )


def guard_archive(
    zip_bytes: bytes,
    *,
    source: str = "archive",
    current_depth: int = 0,
) -> None:
    """Inspect central directory headers without decompressing payload.

    Raises ArchiveRejectedError if any threshold or safety boundary is violated.
    """
    if current_depth > settings.ARCHIVE_MAX_NESTED_DEPTH:
        raise ArchiveRejectedError(
            f"Archive nesting depth {current_depth} exceeds maximum allowed "
            f"depth ({settings.ARCHIVE_MAX_NESTED_DEPTH})",
            findings=[
                ScanFinding(
                    source=source,
                    verdict=ScanVerdict.SUSPICIOUS,
                    reason="excessive_nesting",
                    detail={"depth": current_depth},
                )
            ],
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ArchiveRejectedError(
            f"Invalid or corrupted zip archive: {exc}",
            findings=[
                ScanFinding(
                    source=source,
                    verdict=ScanVerdict.MALICIOUS,
                    reason="corrupt_archive",
                    detail={"error": str(exc)},
                )
            ],
        ) from exc

    with zf:
        members = zf.infolist()

        # 1. Total entry count check
        if len(members) > settings.ARCHIVE_MAX_ENTRIES:
            raise ArchiveRejectedError(
                f"Archive entry count {len(members)} exceeds limit of {settings.ARCHIVE_MAX_ENTRIES}",
                findings=[
                    ScanFinding(
                        source=source,
                        verdict=ScanVerdict.MALICIOUS,
                        reason="entry_count_cap",
                        detail={"entry_count": len(members)},
                    )
                ],
            )

        total_uncompressed = 0
        nested_archives: list[zipfile.ZipInfo] = []

        for member in members:
            # 2. Path safety check
            _validate_member_filename(member.filename)

            # 3. Encryption check
            if member.flag_bits & 0x1:
                raise ArchiveRejectedError(
                    f"Encrypted zip entries are not permitted: {member.filename!r}",
                    findings=[
                        ScanFinding(
                            source=source,
                            verdict=ScanVerdict.SUSPICIOUS,
                            reason="encrypted_entry",
                            detail={"filename": member.filename},
                        )
                    ],
                )

            # 4. Single entry size cap
            if member.file_size > settings.ARCHIVE_MAX_UNCOMPRESSED_BYTES:
                raise ArchiveRejectedError(
                    f"Entry {member.filename!r} uncompressed size ({member.file_size} bytes) "
                    f"exceeds maximum allowed ({settings.ARCHIVE_MAX_UNCOMPRESSED_BYTES} bytes)",
                    findings=[
                        ScanFinding(
                            source=source,
                            verdict=ScanVerdict.MALICIOUS,
                            reason="oversized_uncompressed",
                            detail={
                                "filename": member.filename,
                                "file_size": member.file_size,
                            },
                        )
                    ],
                )

            total_uncompressed += member.file_size

            # 5. Compression ratio check (zip bomb defense)
            if member.compress_size > 0:
                ratio = member.file_size / member.compress_size
                if ratio > settings.ARCHIVE_MAX_RATIO and member.file_size > 1024 * 1024:
                    raise ArchiveRejectedError(
                        f"Entry {member.filename!r} compression ratio {ratio:.1f}:1 exceeds "
                        f"limit of {settings.ARCHIVE_MAX_RATIO}:1 (potential zip bomb)",
                        findings=[
                            ScanFinding(
                                source=source,
                                verdict=ScanVerdict.MALICIOUS,
                                reason="ratio_bomb",
                                detail={
                                    "filename": member.filename,
                                    "ratio": ratio,
                                    "file_size": member.file_size,
                                },
                            )
                        ],
                    )

            # 6. Detect nested archives
            ext = "." + member.filename.rsplit(".", 1)[-1].lower() if "." in member.filename else ""
            if ext in _ARCHIVE_EXTENSIONS and member.file_size > 0:
                nested_archives.append(member)

        # 7. Total archive uncompressed size cap
        if total_uncompressed > settings.ARCHIVE_MAX_UNCOMPRESSED_BYTES:
            raise ArchiveRejectedError(
                f"Total uncompressed size {total_uncompressed} bytes exceeds limit of "
                f"{settings.ARCHIVE_MAX_UNCOMPRESSED_BYTES} bytes (potential zip bomb)",
                findings=[
                    ScanFinding(
                        source=source,
                        verdict=ScanVerdict.MALICIOUS,
                        reason="oversized_uncompressed",
                        detail={"total_uncompressed": total_uncompressed},
                    )
                ],
            )

        # 8. Check nested archives recursively
        for nested in nested_archives:
            nested_bytes = zf.read(nested)
            guard_archive(
                nested_bytes,
                source=f"{source}:{nested.filename}",
                current_depth=current_depth + 1,
            )


def safe_extract_zip(zip_bytes: bytes, dest: Path) -> Path:
    """Safely extract zip archive to dest directory.

    Guarantees:
    - Calls guard_archive first (zip-bomb, encryption, ratio, path traversal verification)
    - Normalizes paths and verifies extraction stays inside dest
    - Streams entries safely using shutil.copyfileobj
    - Unwraps single root directory if present (e.g. GitHub archives)
    """
    guard_archive(zip_bytes, source="safe_extract")

    dest_resolved = dest.resolve()
    dest_resolved.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            # Validate path before extraction
            _validate_member_filename(member.filename)

            # Compute and verify destination path
            target_path = (dest_resolved / member.filename).resolve()
            try:
                target_path.relative_to(dest_resolved)
            except ValueError as exc:
                raise ArchiveRejectedError(
                    f"Path traversal detected: {member.filename!r} escapes destination {dest_resolved}",
                    findings=[
                        ScanFinding(
                            source="archive",
                            verdict=ScanVerdict.MALICIOUS,
                            reason="archive_traversal",
                            detail={"filename": member.filename},
                        )
                    ],
                ) from exc

            if member.is_dir() or member.filename.endswith("/"):
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source_stream, open(target_path, "wb") as target_file:
                    shutil.copyfileobj(source_stream, target_file)

    # Unwrap single root folder if created by GitHub zipball
    subdirs = [p for p in dest_resolved.iterdir() if p.is_dir() and not p.name.startswith(".")]
    files = [p for p in dest_resolved.iterdir() if p.is_file()]
    if len(subdirs) == 1 and len(files) == 0:
        return subdirs[0]

    return dest_resolved
