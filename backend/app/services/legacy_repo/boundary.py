"""
AI Solution Builder — Legacy Repository Boundary & Protection Guardrails

Strictly enforces that `sutra_os` is never touched, read for modernization,
modified, or targeted under any circumstances.
"""

from pathlib import Path

FORBIDDEN_PATHS = {"sutra_os", ".git"}


class ScopeBoundaryViolation(PermissionError):
    """Raised when an operation attempts to touch a restricted area such as sutra_os."""


def is_path_safe(target_path: str | Path) -> bool:
    """Return True if path is safe to inspect or modify, False if it touches sutra_os or restricted areas."""
    try:
        p = Path(target_path).resolve()
        parts = {part.lower() for part in p.parts}
        return "sutra_os" not in parts
    except Exception:
        return False


def assert_safe_boundary(target_path: str | Path, action: str = "access") -> Path:
    """Validate that target_path does NOT touch or reside inside sutra_os.

    Raises ScopeBoundaryViolation if target_path enters sutra_os.
    Returns the resolved Path if safe.
    """
    p = Path(target_path).resolve()
    parts = {part.lower() for part in p.parts}

    if "sutra_os" in parts:
        raise ScopeBoundaryViolation(
            f"ABSOLUTE SCOPE RESTRICTION: Attempted to {action} forbidden directory 'sutra_os'. "
            f"Path '{target_path}' is completely off-limits and cannot be modified, analyzed, or accessed."
        )

    return p
