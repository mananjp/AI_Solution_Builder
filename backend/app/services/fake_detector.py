"""
AI Solution Builder — Fake Implementation Detector

The build pipeline could report "complete" while shipping an app that only
looks alive: endpoints that echo a canned response, seed rows copied from a
sample app, data kept in a process variable that resets on restart.

This module finds that before the user does. It is deliberately dumb and
deterministic — pattern matching over generated source — so it cannot be
talked out of a verdict by the model that wrote the code.

Severity:
  blocker  -> the app does not do its job; never ship as complete
  warning  -> suspicious; surface to the user but allow
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Sample data from other domains that must never appear in a generated app.
# These are the fingerprints of a template rather than a real build.
_FOREIGN_SEED_TERMS = [
    "madagascar vanilla",
    "belgian dark chocolate",
    "sarah jenkins",
    "david chen",
    "elena rostova",
    "john doe",
    "jane doe",
    "acme corp",
    "lorem ipsum",
    "foo@bar.com",
    "test@example.com",
]

# An action handler that returns a constant instead of computing anything.
_ECHO_ACTION = re.compile(r'status:\s*["\'](completed|success|ok)["\']', re.IGNORECASE)
_RETURNS_OUTPUT_EXAMPLE = re.compile(r"result:\s*\{", re.IGNORECASE)

# State that evaporates when the process restarts.
_IN_MEMORY_STORE = re.compile(
    r"(globalThis as unknown as|new Map\(\)|private tables|__dataStore|global\.__db)",
)

_STUB_MARKERS = [
    (re.compile(r"HTTPException\([^)]*?501", re.S), "an action that was never implemented"),
    (re.compile(r"\bTODO\b|\bFIXME\b"), "unfinished work left in the code"),
    (re.compile(r"not implemented", re.IGNORECASE), "an action that was never implemented"),
    (re.compile(r"__MODULE_LINKS__|__APP_TITLE__|@@[A-Z_]+@@"), "leftover template placeholders"),
]


@dataclass
class Finding:
    severity: str  # blocker | warning
    where: str
    what: str  # plain-language description for the user
    detail: str = ""  # technical detail for the repair prompt

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "where": self.where,
            "what": self.what,
            "detail": self.detail,
        }


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def detect_fake_data(root: Path, spec: Any = None) -> list[Finding]:
    """Seed rows that belong to a different app than the one requested."""
    findings: list[Finding] = []
    allowed = set()
    for record in getattr(spec, "seed_data", []) or []:
        for value in (getattr(record, "values", {}) or {}).values():
            if isinstance(value, str):
                allowed.add(value.strip().lower())

    for source in list(root.rglob("*.ts")) + list(root.rglob("*.tsx")) + list(root.rglob("*.py")):
        if "node_modules" in source.parts:
            continue
        lowered = _read(source).lower()
        for term in _FOREIGN_SEED_TERMS:
            if term in lowered and term not in allowed:
                findings.append(
                    Finding(
                        severity="blocker",
                        where=_rel(source, root),
                        what=(
                            "The app is pre-filled with example information from a different "
                            f"sample app ({term!r}), not from your business."
                        ),
                        detail=f"Foreign sample data {term!r} found in {_rel(source, root)}.",
                    )
                )
                break
    return findings


def detect_fake_actions(root: Path, spec: Any = None) -> list[Finding]:
    """Action handlers that return a canned answer instead of doing the work."""
    findings: list[Finding] = []
    action_names = {str(getattr(a, "name", "")) for a in (getattr(spec, "actions", []) or [])}
    summaries = {
        str(getattr(a, "name", "")): str(getattr(a, "summary", ""))
        for a in (getattr(spec, "actions", []) or [])
    }

    for route in root.rglob("route.ts"):
        if "node_modules" in route.parts:
            continue
        if "actions" not in route.parts:
            continue
        body = _read(route)
        name = route.parent.name
        if _ECHO_ACTION.search(body) and _RETURNS_OUTPUT_EXAMPLE.search(body):
            findings.append(
                Finding(
                    severity="blocker",
                    where=_rel(route, root),
                    what=(
                        f"'{summaries.get(name, name)}' pretends to work — it always replies "
                        "with the same example answer instead of actually working it out."
                    ),
                    detail=(
                        f"Action '{name}' handler returns a constant output_example; "
                        "no computation, no data access."
                    ),
                )
            )

    actions_py = root / "backend" / "actions.py"
    if actions_py.exists() and action_names:
        body = _read(actions_py)
        for pattern, label in _STUB_MARKERS[:1]:  # 501 stubs
            if pattern.search(body):
                findings.append(
                    Finding(
                        severity="blocker",
                        where="backend/actions.py",
                        what="Part of the app that should do the real work was left unfinished.",
                        detail=f"{label} in backend/actions.py",
                    )
                )
    return findings


def detect_volatile_storage(root: Path) -> list[Finding]:
    """Data kept in process memory — lost on every restart, shared between users."""
    findings: list[Finding] = []
    for source in list(root.rglob("*.ts")) + list(root.rglob("*.tsx")):
        if "node_modules" in source.parts:
            continue
        body = _read(source)
        if _IN_MEMORY_STORE.search(body) and re.search(r"\b(list|insert|update|delete)\b", body):
            findings.append(
                Finding(
                    severity="blocker",
                    where=_rel(source, root),
                    what=(
                        "Anything your customers enter would be wiped every time the app "
                        "restarts, because it is never actually saved anywhere."
                    ),
                    detail=(
                        f"In-memory store in {_rel(source, root)} backs read/write operations; "
                        "no database."
                    ),
                )
            )
    return findings


def detect_unfinished(root: Path) -> list[Finding]:
    """Placeholders and stubs left in shipped source."""
    findings: list[Finding] = []
    for source in list(root.rglob("*.tsx")) + list(root.rglob("*.py")):
        if "node_modules" in source.parts or "tests" in source.parts:
            continue
        body = _read(source)
        for pattern, label in _STUB_MARKERS[1:]:
            if pattern.search(body):
                findings.append(
                    Finding(
                        severity="warning",
                        where=_rel(source, root),
                        what=f"There is {label} in the app.",
                        detail=f"{label} in {_rel(source, root)}",
                    )
                )
                break
    return findings


def detect_disconnected_screens(root: Path, spec: Any = None) -> list[Finding]:
    """Screens that never load real information — a picture of an app."""
    findings: list[Finding] = []
    app_dir = root / "frontend" / "src" / "app"
    if not app_dir.exists():
        return findings

    for screen in getattr(spec, "screens", []) or []:
        route = str(getattr(screen, "route", "/")).strip("/")
        page = app_dir / route / "page.tsx" if route else app_dir / "page.tsx"
        if not page.exists():
            findings.append(
                Finding(
                    severity="blocker",
                    where=f"frontend/src/app/{route or ''}/page.tsx",
                    what=f"The '{getattr(screen, 'name', route)}' screen was never built.",
                    detail=f"Missing page for screen route /{route}",
                )
            )
            continue
        body = _read(page)
        talks_to_server = ("api." in body) or ("fetch(" in body)
        has_inline_rows = re.search(r"=\s*\[\s*\{[^\]]{80,}\]", body, re.S) is not None
        if not talks_to_server:
            findings.append(
                Finding(
                    severity="blocker",
                    where=_rel(page, root),
                    what=(
                        f"The '{getattr(screen, 'name', route)}' screen only shows a fixed "
                        "picture — it never loads or saves anything."
                    ),
                    detail=f"{_rel(page, root)} makes no API calls.",
                )
            )
        elif has_inline_rows:
            findings.append(
                Finding(
                    severity="warning",
                    where=_rel(page, root),
                    what=(
                        f"The '{getattr(screen, 'name', route)}' screen has example rows "
                        "written into it that will show even when it is empty."
                    ),
                    detail=f"{_rel(page, root)} contains a large inline array literal.",
                )
            )
    return findings


def detect_untested_core(root: Path, spec: Any = None) -> list[Finding]:
    """The app's whole point must be covered by a real test."""
    findings: list[Finding] = []
    actions = list(getattr(spec, "actions", []) or [])
    if not actions:
        return findings
    tests_file = root / "backend" / "tests" / "test_acceptance.py"
    body = _read(tests_file)
    if not body:
        findings.append(
            Finding(
                severity="blocker",
                where="backend/tests/",
                what="Nothing checks that your app actually does its job.",
                detail="No acceptance tests generated.",
            )
        )
        return findings
    for action in actions:
        path = str(getattr(action, "path", ""))
        stem = path.split("/")[-1] or str(getattr(action, "name", ""))
        if stem and stem not in body:
            findings.append(
                Finding(
                    severity="blocker",
                    where="backend/tests/test_acceptance.py",
                    what=(
                        f"'{getattr(action, 'summary', stem)}' is never checked, so nobody "
                        "knows whether it works."
                    ),
                    detail=f"No acceptance test exercises action path {path}.",
                )
            )
    return findings


def audit_build(workspace_dir: Path | str, spec: Any = None) -> list[Finding]:
    """Run every check. Blockers mean the build must not be called complete."""
    root = Path(workspace_dir)
    findings: list[Finding] = []
    findings += detect_volatile_storage(root)
    findings += detect_fake_actions(root, spec)
    findings += detect_constant_actions(root, spec)
    findings += detect_fake_data(root, spec)
    findings += detect_disconnected_screens(root, spec)
    findings += detect_untested_core(root, spec)
    findings += detect_unfinished(root)
    return findings


def blockers(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "blocker"]


def plain_summary(findings: list[Finding]) -> str:
    """What to tell a non-technical user when a build is held back."""
    blocking = blockers(findings)
    if not blocking:
        return "Everything checks out — your app really does what we agreed."
    lines = ["I stopped short of calling this finished, because:"]
    seen: set[str] = set()
    for finding in blocking:
        if finding.what in seen:
            continue
        seen.add(finding.what)
        lines.append(f"- {finding.what}")
    lines.append("")
    lines.append("I'm fixing these now rather than handing you something that only looks right.")
    return "\n".join(lines)


def repair_brief(findings: list[Finding]) -> str:
    """Technical instructions for the coding agent's repair turn."""
    blocking = blockers(findings)
    if not blocking:
        return ""
    lines = ["These problems make the app fake rather than working. Fix the root cause:"]
    for finding in blocking:
        lines.append(f"- [{finding.where}] {finding.detail or finding.what}")
    lines += [
        "",
        "Rules:",
        "- Every action must compute its answer from saved data. Never return a constant.",
        "- Every screen must load and save through the server, never a local array.",
        "- Saved information must survive a restart.",
        "- Do not add sample rows from any other app.",
    ]
    return "\n".join(lines)


def write_report(workspace_dir: Path | str, findings: list[Finding]) -> Path:
    """Persist the audit next to the build for the UI and for debugging."""
    root = Path(workspace_dir)
    report = root / "build_audit.json"
    report.write_text(
        json.dumps(
            {
                "blockers": [f.as_dict() for f in findings if f.severity == "blocker"],
                "warnings": [f.as_dict() for f in findings if f.severity == "warning"],
                "summary": plain_summary(findings),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return report


# ── Constant-return actions (the self-confirming test loop) ─────────────
#
# The generated stub used to `return <output_example>` — exactly what the
# generated acceptance test asserted. So the test passed, the gate went green,
# and the shipped app replied with the same number to every request. An action
# body that never touches the database cannot be doing its job.

import ast  # noqa: E402


def _function_is_constant(node: ast.AST) -> bool:
    """True when a function body never reads data and just returns a literal."""
    touches_data = False
    returns_literal = False
    for child in ast.walk(node):
        if isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)):
            touches_data = True
        if isinstance(child, ast.Name) and child.id in ("session", "select", "func", "models"):
            touches_data = True
        if isinstance(child, ast.Return) and isinstance(
            child.value, (ast.Dict, ast.Constant, ast.List)
        ):
            returns_literal = True
    return returns_literal and not touches_data


def detect_constant_actions(root: Path, spec: Any = None) -> list[Finding]:
    """Action handlers in backend/actions.py that return a fixed answer."""
    findings: list[Finding] = []
    actions_py = Path(root) / "backend" / "actions.py"
    if not actions_py.exists():
        return findings
    try:
        tree = ast.parse(_read(actions_py))
    except SyntaxError as exc:
        return [
            Finding(
                severity="blocker",
                where="backend/actions.py",
                what="The part of the app that does the real work is broken.",
                detail=f"SyntaxError in backend/actions.py: {exc}",
            )
        ]

    summaries = {
        str(getattr(a, "name", "")): str(getattr(a, "summary", ""))
        for a in (getattr(spec, "actions", []) or [])
    }
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _function_is_constant(node):
            continue
        label = summaries.get(node.name, node.name.replace("_", " "))
        findings.append(
            Finding(
                severity="blocker",
                where="backend/actions.py",
                what=(
                    f"'{label}' always gives the same answer no matter what you enter — "
                    "it never actually looks at your information."
                ),
                detail=(
                    f"Action '{node.name}' returns a literal and never touches the session; "
                    "it is a placeholder, not an implementation."
                ),
            )
        )
    return findings
