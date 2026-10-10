"""Regression coverage for archive extraction security boundaries."""

from __future__ import annotations

import io
import stat
import zipfile
from pathlib import Path

import pytest

from app.services.security.archive import safe_extract_zip
from app.services.security.types import ArchiveRejectedError


def _zip_with_member(name: str, content: bytes, *, mode: int | None = None) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        info = zipfile.ZipInfo(name)
        if mode is not None:
            info.create_system = 3
            info.external_attr = mode << 16
        archive.writestr(info, content)
    return payload.getvalue()


def test_safe_extract_rejects_zip_slip(tmp_path: Path) -> None:
    with pytest.raises(ArchiveRejectedError, match="traversal"):
        safe_extract_zip(_zip_with_member("../outside.txt", b"nope"), tmp_path)


def test_safe_extract_rejects_symbolic_links(tmp_path: Path) -> None:
    symlink_mode = stat.S_IFLNK | 0o777
    with pytest.raises(ArchiveRejectedError, match="Symbolic-link"):
        safe_extract_zip(_zip_with_member("link", b"/etc/passwd", mode=symlink_mode), tmp_path)


def test_safe_extract_strips_executable_mode_and_unwraps_root(tmp_path: Path) -> None:
    executable_mode = stat.S_IFREG | 0o755
    root = safe_extract_zip(
        _zip_with_member("github-project/run.sh", b"echo safe\n", mode=executable_mode), tmp_path
    )

    extracted = root / "run.sh"
    assert root.name == "github-project"
    assert extracted.read_bytes() == b"echo safe\n"
    assert extracted.stat().st_mode & 0o111 == 0
