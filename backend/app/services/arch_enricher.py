"""Architecture enrichment for solution artifacts.

The deterministic artifact synthesizer produces structurally correct but generic
architecture prose: every app gets the same canned components, the same "2 week"
phases and the same boilerplate overview. It is derived only from entity names,
so two unrelated apps receive identical HLD/LLD/roadmap text.

This module asks the OpenCode sidecar — the same high-quality model that writes
the generated code — to draft the architecture narrative from the *confirmed*
spec (entities, actions, screens). The spec already exists and is validated by
that point, so the result is grounded rather than invented.

Failure policy: any error, timeout, empty response or missing section falls back
to the deterministic artifacts the caller already computed. Enrichment is an
upgrade, never a new way for a build or a chat turn to fail.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services import mvp_builder

logger = logging.getLogger(__name__)

# Keys this module is allowed to overwrite. Anything not listed is left exactly
# as the deterministic synthesizer produced it, so a malformed LLM response can
# never corrupt structured artifacts (ER diagram, schema DDL, endpoints).
_ENRICHABLE: frozenset[str] = frozenset({"hld", "lld", "roadmap"})

_ARCHITECT_SYSTEM = """You are a principal architect. From the CONFIRMED SPEC below, produce \
spec-specific design documents. Reference the spec's real entities, actions and \
screens — never generic filler that fits any app.

Return ONLY a JSON object, no markdown fences:

{
  "hld": {
    "title": "High-Level Design — <app>",
    "system_overview": "3-4 sentences: what it does, who uses it, the one architectural idea that makes it work.",
    "components": [{"name": "N", "technology": "T", "description": "its responsibility in THIS app, naming real entities"}],
    "integrations": [{"from": "A", "to": "B", "protocol": "REST|SQL", "description": "the concrete exchange"}],
    "deployment": {"environment": "Docker/Render", "services": ["s"], "scaling_strategy": "why it fits this app"},
    "security": {"authentication": "scheme", "authorization": "model", "encryption": "controls"},
    "architecture_pattern": "pattern + one-line justification",
    "decisions": [{"topic": "t", "choice": "c", "rationale": "r", "alternatives": ["a"], "impact": "high|medium|low"}]
  },
  "lld": {
    "title": "Low-Level Design — <app>",
    "modules": [{"name": "module_slug", "description": "responsibility", "endpoints": [{"method": "GET", "path": "/api/v1/x", "description": "d"}], "data_models": ["entity"]}]
  },
  "roadmap": {
    "title": "Sprint Roadmap — <app>",
    "phases": [{"name": "Phase n: ...", "duration": "n weeks", "deliverables": ["concrete"], "milestones": ["concrete"]}],
    "total_duration": "n weeks"
  }
}

Rules: components/modules must map to the spec's real modules and entities; LLD \
endpoints must match the spec's API surface; no TBD, placeholders or lorem ipsum; \
4-8 components, 4-8 modules, 3-5 phases."""


def _spec_summary(spec: dict[str, Any], title: str, industry: str) -> str:
    """Render the confirmed spec as compact, faithful text for the architect prompt."""
    lines: list[str] = [
        f"Application name: {title}",
        f"Industry: {industry}",
    ]
    modules = spec.get("confirmed_modules") or spec.get("identified_solutions") or []
    if modules:
        lines.append(f"Modules: {', '.join(str(m) for m in modules)}")

    entities = (
        ((spec.get("er_diagram") or {}).get("content") or {}).get("entities")
        or spec.get("entities")
        or []
    )
    if entities:
        lines.append("Entities:")
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            fields = ent.get("fields") or []
            names = [
                (f.get("name") if isinstance(f, dict) else str(f))
                for f in fields
                if isinstance(f, (dict, str))
            ]
            lines.append(f"  - {ent.get('name')}: {', '.join(str(n) for n in names if n)}")

    actions = spec.get("actions") or []
    if actions:
        lines.append("Business actions:")
        for act in actions:
            if isinstance(act, dict):
                lines.append(
                    f"  - {act.get('name')} {act.get('method')} {act.get('path')}: {act.get('summary', '')}"
                )

    screens = spec.get("screens") or []
    if screens:
        lines.append("Screens:")
        for scr in screens:
            if isinstance(scr, dict):
                lines.append(
                    f"  - {scr.get('name')} ({scr.get('route')}): {scr.get('purpose', '')}"
                )

    return "\n".join(lines)


def _coerce(value: Any) -> dict[str, Any] | None:
    """Accept either a dict or a JSON string (models sometimes wrap in fences)."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return value if isinstance(value, dict) else None


async def _ask_opencode(spec_text: str) -> dict[str, Any]:
    """One OpenCode session dedicated to drafting the architecture documents."""
    if not settings.OPENCODE_ARCH_ENRICH:
        raise RuntimeError("architecture enrichment disabled by configuration")

    session_id = await mvp_builder.create_session("architecture-enrichment")
    try:
        response = await mvp_builder.send_message(
            session_id,
            f"{_ARCHITECT_SYSTEM}\n\nCONFIRMED SPECIFICATION:\n{spec_text}\n\nReturn the JSON object only.",
            timeout=settings.OPENCODE_ARCH_TIMEOUT,
        )
    finally:
        if session_id:
            await mvp_builder.abort_session(session_id)

    # The sidecar returns a message body; text may be at the top level or in parts.
    parts = response.get("parts") if isinstance(response, dict) else None
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text", "")))
    if not texts and isinstance(response, dict):
        info = response.get("info") or {}
        if isinstance(info, dict) and info.get("error"):
            raise RuntimeError(f"sidecar returned an error: {info['error']}")
    raw = "\n".join(t for t in texts if t).strip()
    if not raw:
        raise RuntimeError("sidecar returned no text")

    cleaned = raw
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0]

    payload = _coerce(cleaned.strip())
    if payload is None:
        raise RuntimeError("sidecar response was not a JSON object")
    return payload


async def enrich_architecture(
    base: dict[str, Any],
    spec: dict[str, Any],
    title: str,
    industry: str,
) -> dict[str, Any]:
    """Return ``base`` with a spec-grounded HLD/LLD/roadmap when OpenCode is available.

    ``base`` already contains the deterministic artifacts. Only ``hld``, ``lld``
    and ``roadmap`` are ever replaced, and only when the sidecar returns a
    parseable object with the expected top-level sections. Everything else is
    returned untouched.
    """
    merged: dict[str, Any] = dict(base)
    try:
        spec_text = _spec_summary(spec, title, industry)
        generated = await _ask_opencode(spec_text)
    except Exception as exc:
        logger.info("Architecture enrichment skipped (%s); keeping deterministic artifacts", exc)
        return merged

    replaced: list[str] = []
    for key in ("hld", "lld", "roadmap"):
        section = _coerce(generated.get(key))
        if not section:
            continue
        entry = dict(base.get(key) or {})
        # Preserve the deterministic structural keys the UI depends on.
        entry.setdefault("artifact_type", key)
        entry["title"] = section.get("title") or entry.get("title")
        entry["content"] = section
        entry["content_text"] = _render(key, section)
        merged[key] = entry
        replaced.append(key)

    if replaced:
        logger.info("Architecture enriched via OpenCode: %s", ", ".join(replaced))
    return merged


def _render(key: str, section: dict[str, Any]) -> str:
    """Markdown rendering of an enriched section, tolerant of missing fields."""
    title = str(section.get("title") or key.upper())
    out = [f"# {title}", ""]
    overview = section.get("system_overview")
    if overview:
        out += [str(overview), ""]

    for group, label in (
        ("components", "Components"),
        ("integrations", "Integrations"),
        ("modules", "Modules"),
        ("phases", "Phases"),
        ("decisions", "Decisions"),
    ):
        items = section.get(group)
        if not isinstance(items, list) or not items:
            continue
        out.append(f"## {label}")
        for item in items:
            if isinstance(item, dict):
                head = item.get("name") or item.get("topic") or item.get("from") or "Item"
                detail = (
                    item.get("description") or item.get("rationale") or item.get("choice") or ""
                )
                out.append(f"- **{head}**{f': {detail}' if detail else ''}")
            else:
                out.append(f"- {item}")
        out.append("")

    ddl = section.get("phases")
    if key == "roadmap" and isinstance(ddl, list):
        total = section.get("total_duration")
        if total:
            out += ["", f"**Total duration:** {total}"]

    return "\n".join(out).strip()
