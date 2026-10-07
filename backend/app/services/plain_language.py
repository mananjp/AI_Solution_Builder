"""
AI Solution Builder — Plain Language Layer

Everything a non-technical user reads goes through here. The AppSpec is a
technical artefact (entities, enums, refs, endpoints); this module renders it
as ordinary sentences, and lints anything we are about to show the user for
developer jargon.

Two directions:
  spec  -> plain English   (describe_spec, describe_change, describe_progress)
  words -> safe wording    (lint_for_jargon, dejargon)

No LLM calls here on purpose: this is deterministic, testable, and cannot
hallucinate a feature the spec does not contain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Words that must never reach a non-technical user. Maps jargon -> plain word.
# Keys are matched case-insensitively on word boundaries.
JARGON: dict[str, str] = {
    "entity": "kind of information",
    "entities": "kinds of information",
    "schema": "structure",
    "enum": "fixed list of choices",
    "boolean": "yes/no",
    "bool": "yes/no",
    "integer": "whole number",
    "int": "whole number",
    "float": "number",
    "varchar": "text",
    "nullable": "optional",
    "foreign key": "link",
    "primary key": "unique id",
    "crud": "add, view, edit and delete",
    "endpoint": "action",
    "endpoints": "actions",
    "api": "connection",
    "rest": "connection",
    "backend": "the part that stores your data",
    "frontend": "the screens people see",
    "deploy": "put online",
    "deployment": "putting it online",
    "repository": "code folder",
    "repo": "code folder",
    "migration": "database update",
    "payload": "information sent",
    "json": "data",
    "sql": "database",
    "query": "lookup",
    "authentication": "sign-in",
    "auth": "sign-in",
    "rbac": "who can do what",
    "middleware": "behind-the-scenes step",
    "scaffold": "starter version",
    "scaffolding": "building the starter version",
    "pydantic": "data checking",
    "sqlalchemy": "database tool",
    "fastapi": "the server",
    "next.js": "the website",
    "tsx": "screen file",
    "component": "screen piece",
    "null": "empty",
    "boolean flag": "yes/no switch",
    "instantiate": "create",
    "persist": "save",
    "persistence": "saving",
    "idempotent": "safe to repeat",
    "async": "",
    "http": "",
    "uuid": "unique id",
}

# Field types -> how we describe them to a human.
_TYPE_WORDS: dict[str, str] = {
    "string": "text",
    "text": "longer text",
    "int": "a whole number",
    "float": "a number",
    "bool": "yes or no",
    "date": "a date",
    "datetime": "a date and time",
    "enum": "one of a few choices",
    "ref": "a link to",
}

_JARGON_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(k) for k in JARGON), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Technical shapes that should never appear in user-facing copy.
_CODE_SHAPES = [
    (re.compile(r"\b[a-z_]+\.(py|tsx|ts|json|sql)\b"), "a file name"),
    (re.compile(r"\b(GET|POST|PATCH|DELETE|PUT)\s+/"), "an HTTP route"),
    (re.compile(r"/api/v\d"), "an API path"),
    (re.compile(r"\b\w+_id\b"), "a database column"),
    (re.compile(r"[{}<>]{2,}|```"), "code formatting"),
]


@dataclass
class JargonHit:
    term: str
    suggestion: str
    kind: str = "word"


def lint_for_jargon(text: str) -> list[JargonHit]:
    """Return every developer term found in user-facing text.

    Used to gate anything we show a non-technical user, including LLM output.
    """
    hits: list[JargonHit] = []
    seen: set[str] = set()
    for match in _JARGON_RE.finditer(text or ""):
        term = match.group(0)
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        hits.append(JargonHit(term=term, suggestion=JARGON.get(key, "")))
    for pattern, label in _CODE_SHAPES:
        found = pattern.search(text or "")
        if found and found.group(0).lower() not in seen:
            seen.add(found.group(0).lower())
            hits.append(JargonHit(term=found.group(0), suggestion="", kind=label))
    return hits


def dejargon(text: str) -> str:
    """Swap known developer words for plain ones, preserving sentence case."""

    def _swap(match: re.Match[str]) -> str:
        original = match.group(0)
        replacement = JARGON.get(original.lower(), original)
        if not replacement:
            return original
        if original[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    return _JARGON_RE.sub(_swap, text or "")


def _humanize(name: str) -> str:
    """`paid_by_id` -> `paid by`, `menu_items` -> `menu items`."""
    cleaned = re.sub(r"_id$", "", str(name or ""))
    return cleaned.replace("_", " ").strip()


def _a_or_an(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def describe_field(field: Any, spec: Any = None) -> str:
    """One plain sentence fragment for a single field."""
    label = _humanize(getattr(field, "name", ""))
    ftype = getattr(field, "type", "string")
    if ftype == "enum":
        values = [str(v).replace("_", " ") for v in getattr(field, "enum_values", [])]
        choices = ", ".join(values[:-1]) + " or " + values[-1] if len(values) > 1 else "".join(values)
        return f"{label} ({choices})"
    if ftype == "ref":
        target = _humanize(getattr(field, "ref", "") or "")
        return f"{label} (which {target} it belongs to)"
    word = _TYPE_WORDS.get(ftype, "text")
    optional = "" if getattr(field, "required", True) else ", optional"
    return f"{label} ({word}{optional})"


def describe_entity(entity: Any) -> str:
    """'For every Customer you can record: name (text), phone (text).'"""
    label = _humanize(getattr(entity, "plural", "") or getattr(entity, "name", ""))
    fields = [f for f in getattr(entity, "fields", []) if getattr(f, "name", "") != "id"]
    parts = [describe_field(f) for f in fields]
    if not parts:
        return f"{label.capitalize()}"
    return f"{label.capitalize()} — you can record " + ", ".join(parts)


def describe_action(action: Any) -> str:
    """'Work out who owes what — this is the part that does the maths.'"""
    summary = str(getattr(action, "summary", "") or _humanize(getattr(action, "name", "")))
    summary = summary.rstrip(".")
    rules = [str(r) for r in getattr(action, "rules", []) if r]
    if not rules:
        return summary
    return summary + ". It follows these rules: " + "; ".join(dejargon(r).rstrip(".") for r in rules[:4])


def describe_screen(screen: Any) -> str:
    name = str(getattr(screen, "name", "") or "Screen")
    purpose = str(getattr(screen, "purpose", "")).rstrip(".")
    interactions = [str(i).rstrip(".") for i in getattr(screen, "key_interactions", [])]
    line = f"{name} — {purpose}" if purpose else name
    if interactions:
        line += ". People can " + ", ".join(dejargon(i) for i in interactions[:4])
    return line


def describe_spec(spec: Any) -> str:
    """The whole plan in plain English, ready to show before building.

    This is what a non-technical user approves instead of reading a spec file.
    """
    lines: list[str] = []
    name = getattr(spec, "app_name", "Your app")
    one_liner = str(getattr(spec, "one_liner", "")).rstrip(".")
    lines.append(f"**{name}**" + (f" — {one_liner}." if one_liner else ""))

    core = str(getattr(spec, "core_value", "")).rstrip(".")
    if core:
        lines.append("")
        lines.append(f"The thing it actually does for you: {dejargon(core)}.")

    entities = list(getattr(spec, "entities", []))
    if entities:
        lines.append("")
        lines.append("**What it will remember**")
        for entity in entities:
            lines.append(f"- {describe_entity(entity)}")

    actions = list(getattr(spec, "actions", []))
    if actions:
        lines.append("")
        lines.append("**What it will work out for you**")
        for action in actions:
            lines.append(f"- {describe_action(action)}")

    screens = list(getattr(spec, "screens", []))
    if screens:
        lines.append("")
        lines.append("**The screens you'll get**")
        for screen in screens:
            lines.append(f"- {describe_screen(screen)}")

    assumptions = [str(a) for a in getattr(spec, "assumptions", []) if a]
    if assumptions:
        lines.append("")
        lines.append("**I assumed a few things** (tell me if any are wrong)")
        for assumption in assumptions:
            lines.append(f"- {dejargon(assumption)}")

    tests = list(getattr(spec, "acceptance_tests", []))
    if tests:
        lines.append("")
        lines.append("**How I'll check it really works**")
        for test in tests:
            lines.append(f"- {str(getattr(test, 'description', '')).rstrip('.')}")

    return "\n".join(lines)


# ── Build progress, in human terms ──────────────────────────────────────

_PROGRESS_WORDS: dict[str, str] = {
    "analyzing": "Working out exactly what your app needs to do",
    "designing": "Choosing the colours and layout",
    "scaffolding": "Setting up the basic structure",
    "coding": "Writing the parts that do the real work",
    "verifying": "Testing it the way a real customer would use it",
    "repairing": "Found a problem — fixing it now",
    "packaging": "Wrapping it up ready to go online",
    "deploying": "Putting it online",
    "complete": "Done — your app is ready",
}


def describe_progress(phase: str, detail: str = "") -> str:
    """Turn an internal phase name into something a shop owner understands."""
    base = _PROGRESS_WORDS.get(phase, dejargon(phase.replace("_", " ")).capitalize())
    if not detail:
        return base
    return f"{base} ({dejargon(detail)})"


def describe_test_results(passed: int, failed: int) -> str:
    """Plain summary of the acceptance test run."""
    total = passed + failed
    if total == 0:
        return "I haven't been able to test it yet."
    if failed == 0:
        return (
            f"I ran {total} real check{'s' if total != 1 else ''} on your app "
            f"— everything worked."
        )
    return (
        f"I ran {total} checks on your app. {passed} worked, but {failed} didn't. "
        "I'm fixing those before I call it done."
    )


# ── Changes, in human terms ─────────────────────────────────────────────


def describe_change(old_spec: Any, new_spec: Any) -> list[str]:
    """Plain bullet list of what a spec edit will actually change for the user."""
    changes: list[str] = []

    def by_name(items: list[Any]) -> dict[str, Any]:
        return {str(getattr(i, "name", "")): i for i in items}

    old_entities = by_name(list(getattr(old_spec, "entities", [])))
    new_entities = by_name(list(getattr(new_spec, "entities", [])))

    for name in new_entities.keys() - old_entities.keys():
        changes.append(f"Start keeping track of {_humanize(name)}")
    for name in old_entities.keys() - new_entities.keys():
        changes.append(f"Stop keeping track of {_humanize(name)} (existing ones will be removed)")

    for name in new_entities.keys() & old_entities.keys():
        old_fields = {str(getattr(f, "name", "")) for f in getattr(old_entities[name], "fields", [])}
        new_fields = {str(getattr(f, "name", "")) for f in getattr(new_entities[name], "fields", [])}
        for field in sorted(new_fields - old_fields):
            changes.append(f"Record {_humanize(field)} for each {_humanize(name)}")
        for field in sorted(old_fields - new_fields):
            changes.append(f"Stop recording {_humanize(field)} for {_humanize(name)}")

    old_actions = by_name(list(getattr(old_spec, "actions", [])))
    new_actions = by_name(list(getattr(new_spec, "actions", [])))
    for name in new_actions.keys() - old_actions.keys():
        changes.append(f"New: {describe_action(new_actions[name])}")
    for name in old_actions.keys() - new_actions.keys():
        changes.append(f"Remove: {_humanize(name)}")
    for name in new_actions.keys() & old_actions.keys():
        old_rules = [str(r) for r in getattr(old_actions[name], "rules", [])]
        new_rules = [str(r) for r in getattr(new_actions[name], "rules", [])]
        if old_rules != new_rules:
            changes.append(f"Change how {_humanize(name)} works")

    old_screens = {str(getattr(s, "route", "")) for s in getattr(old_spec, "screens", [])}
    new_screens = {str(getattr(s, "route", "")) for s in getattr(new_spec, "screens", [])}
    for route in sorted(new_screens - old_screens):
        match = next(
            (s for s in getattr(new_spec, "screens", []) if str(getattr(s, "route", "")) == route),
            None,
        )
        changes.append(f"Add a new screen: {getattr(match, 'name', route)}")
    for route in sorted(old_screens - new_screens):
        changes.append(f"Remove the screen at {route}")

    return changes


def describe_data_loss(old_spec: Any, new_spec: Any) -> list[str]:
    """Warn, in plain words, about changes that throw away saved information."""
    warnings: list[str] = []
    old_entities = {str(getattr(e, "name", "")): e for e in getattr(old_spec, "entities", [])}
    new_entities = {str(getattr(e, "name", "")): e for e in getattr(new_spec, "entities", [])}

    for name in old_entities.keys() - new_entities.keys():
        warnings.append(f"Everything you've saved under {_humanize(name)} will be deleted.")
    for name in old_entities.keys() & new_entities.keys():
        old_fields = {str(getattr(f, "name", "")) for f in getattr(old_entities[name], "fields", [])}
        new_fields = {str(getattr(f, "name", "")) for f in getattr(new_entities[name], "fields", [])}
        for field in sorted(old_fields - new_fields):
            warnings.append(
                f"The {_humanize(field)} you've recorded for each {_humanize(name)} will be lost."
            )
    return warnings
