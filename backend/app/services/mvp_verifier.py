"""
AI Solution Builder — MVP Build Verification & Bounded Repair Engine

Performs verification checkpoints on generated MVP workspaces before marking builds
complete. Validates Python syntax/AST compilation, project integrity, and frontend
scaffolding. On failure, feeds errors back into the OpenCode session for bounded repair turns
(capped at 1–2 retries) before surfacing actionable errors to the user.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_REPAIR_TURNS = 2


class VerificationError(RuntimeError):
    """Raised when an MVP build fails verification after repair attempts."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def verify_python_syntax(py_file: Path) -> str | None:
    """Compile a Python file to check for syntax and indentation errors."""
    try:
        source = py_file.read_text(encoding="utf-8", errors="replace")
        compile(source, str(py_file), "exec")
        return None
    except SyntaxError as exc:
        line = exc.lineno or 0
        offset = exc.offset or 0
        text = (exc.text or "").strip()
        return f"SyntaxError in {py_file.name}:{line}:{offset}: {exc.msg} (code: '{text}')"
    except Exception as exc:
        return f"Error compiling {py_file.name}: {exc}"


def verify_backend_integrity(backend_dir: Path) -> list[str]:
    """Validate all Python files and scaffold essentials in backend/."""
    errors: list[str] = []
    if not backend_dir.exists():
        return ["Missing backend/ directory in generated workspace"]

    required_files = ["main.py", "models.py", "schemas.py", "routers.py"]
    for req in required_files:
        path = backend_dir / req
        if not path.is_file():
            errors.append(f"Missing required backend file: backend/{req}")
        elif path.stat().st_size == 0:
            errors.append(f"Backend file is empty: backend/{req}")

    # Compile all Python files
    for py_file in sorted(backend_dir.rglob("*.py")):
        if any(part in {".venv", "venv", "__pycache__"} for part in py_file.parts):
            continue
        err = verify_python_syntax(py_file)
        if err:
            errors.append(err)

    # Basic scaffold sanity check in main.py
    main_py = backend_dir / "main.py"
    if main_py.is_file():
        content = main_py.read_text(encoding="utf-8", errors="replace")
        if "FastAPI" not in content:
            errors.append("backend/main.py does not define a FastAPI application")

    return errors


def verify_frontend_integrity(frontend_dir: Path, run_build: bool = False) -> list[str]:
    """Validate frontend project files and package.json."""
    errors: list[str] = []
    if not frontend_dir.exists():
        return ["Missing frontend/ directory in generated workspace"]

    package_json = frontend_dir / "package.json"
    if not package_json.is_file():
        errors.append("Missing required frontend file: frontend/package.json")
    else:
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "dependencies" not in data:
                errors.append("frontend/package.json is missing 'dependencies'")
        except Exception as exc:
            errors.append(f"Invalid JSON in frontend/package.json: {exc}")

    # Check for root page
    page_tsx = frontend_dir / "src" / "app" / "page.tsx"
    page_jsx = frontend_dir / "src" / "app" / "page.jsx"
    page_js = frontend_dir / "src" / "app" / "page.js"
    if not (page_tsx.is_file() or page_jsx.is_file() or page_js.is_file()):
        errors.append("Missing frontend root page (src/app/page.tsx)")

    # Optional: run npm run build if npm is present and requested
    if run_build and shutil.which("npm"):
        try:
            res = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if res.returncode != 0:
                out = (res.stderr or res.stdout or "").strip()
                errors.append(f"Frontend npm build failed: {out[:600]}")
        except subprocess.TimeoutExpired:
            errors.append("Frontend npm build timed out after 90 seconds")
        except Exception as exc:
            logger.warning("Could not execute npm run build: %s", exc)

    return errors


def verify_workspace(workspace_dir: Path, check_npm: bool = False) -> list[str]:
    """Perform comprehensive verification on a generated workspace."""
    errors: list[str] = []
    if not workspace_dir.exists():
        return [f"Workspace directory does not exist: {workspace_dir}"]

    errors.extend(verify_backend_integrity(workspace_dir / "backend"))
    errors.extend(verify_frontend_integrity(workspace_dir / "frontend", run_build=check_npm))
    return errors


async def verify_and_repair(
    workspace_dir: Path,
    session_id: str | None,
    target_dir: str,
    max_repair_turns: int = MAX_REPAIR_TURNS,
    send_prompt_fn: Any = None,
) -> dict[str, Any]:
    """Run verification checkpoint with bounded repair loop.

    1. Checks Python syntax, backend files, and frontend structure.
    2. If errors are found and session_id is live, feeds compiler output back
       into OpenCode for bounded repair turns (up to max_repair_turns).
    3. If verification passes, returns result dict.
    4. If errors persist after the budget, raises VerificationError with real details.
    """
    errors = verify_workspace(workspace_dir)
    if not errors:
        logger.info("Verification passed on initial check for %s", workspace_dir.name)
        return {"verified": True, "repair_turns": 0, "errors": []}

    logger.warning(
        "Build %s failed initial verification with %d error(s): %s",
        workspace_dir.name,
        len(errors),
        errors,
    )

    if not session_id or not send_prompt_fn or max_repair_turns <= 0:
        error_msg = "; ".join(errors)
        raise VerificationError(
            f"Build verification failed: {error_msg}",
            errors=errors,
        )

    for turn in range(1, max_repair_turns + 1):
        logger.info(
            "Starting repair turn %d/%d for session %s (workspace=%s)",
            turn,
            max_repair_turns,
            session_id,
            workspace_dir.name,
        )

        formatted_errors = "\n".join(f"- {e}" for e in errors)
        repair_prompt = (
            f"# Verification Checkpoint Failed — Repair Turn {turn}/{max_repair_turns}\n\n"
            f"The project in `{target_dir}` failed automated verification with the following compiler/linter errors:\n\n"
            f"```\n{formatted_errors}\n```\n\n"
            f"**Your task:** Fix the broken files in `{target_dir}` to resolve these exact errors.\n"
            "- Do not rewrite the whole project or change the directory structure.\n"
            "- Edit only the specific files and lines causing the errors.\n"
            "- Ensure all Python syntax, imports, FastAPI route signatures, and React JSX/TS types are valid.\n"
            "- Report which files you fixed when done."
        )

        try:
            await send_prompt_fn(session_id, repair_prompt)
        except Exception as exc:
            logger.error("Failed to send repair prompt to session %s: %s", session_id, exc)
            break

        # Re-verify after repair turn
        errors = verify_workspace(workspace_dir)
        if not errors:
            logger.info(
                "Build %s passed verification after repair turn %d/%d",
                workspace_dir.name,
                turn,
                max_repair_turns,
            )
            return {"verified": True, "repair_turns": turn, "errors": []}

        logger.warning(
            "Build %s still has %d error(s) after repair turn %d: %s",
            workspace_dir.name,
            len(errors),
            turn,
            errors,
        )

    error_summary = "; ".join(errors[:5])
    raise VerificationError(
        f"Build verification failed after {max_repair_turns} repair attempt(s): {error_summary}",
        errors=errors,
    )
