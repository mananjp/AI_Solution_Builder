"""Tests for OpenCode-backed architecture enrichment."""

from __future__ import annotations

from typing import Any

import pytest

from app.services import arch_enricher
from app.services.arch_enricher import enrich_architecture

SPEC: dict[str, Any] = {
    "industry": "fitness_gym",
    "confirmed_modules": ["members", "classes"],
    "er_diagram": {
        "content": {
            "entities": [
                {"name": "members", "fields": [{"name": "id"}, {"name": "full_name"}]},
                {"name": "classes", "fields": [{"name": "id"}, {"name": "title"}]},
            ]
        }
    },
    "actions": [
        {
            "name": "class_occupancy",
            "method": "GET",
            "path": "/actions/classes/occupancy",
            "summary": "Occupancy per class",
        }
    ],
    "screens": [{"name": "Members", "route": "/members", "purpose": "Manage members"}],
}

# A minimal deterministic artifact set as produced by _synthesize_artifacts_from_spec.
BASE: dict[str, Any] = {
    "industry": "fitness_gym",
    "hld": {
        "artifact_type": "hld",
        "title": "High-Level Design — FitPulse",
        "content": {"system_overview": "canned overview"},
        "content_text": "# High-Level Design — FitPulse\n\ncanned overview",
    },
    "lld": {
        "artifact_type": "lld",
        "title": "Low-Level Design — FitPulse",
        "content": {"modules": []},
        "content_text": "# Low-Level Design — FitPulse",
    },
    "roadmap": {
        "artifact_type": "roadmap",
        "title": "Sprint Roadmap — FitPulse",
        "content": {"phases": []},
        "content_text": "# Sprint Roadmap — FitPulse",
    },
    # Structured artifacts must never be touched by enrichment.
    "er_diagram": {
        "artifact_type": "er_diagram",
        "content": {"entities": SPEC["er_diagram"]["content"]["entities"]},
    },
    "database_schema": {
        "artifact_type": "database_schema",
        "content": {"ddl": "CREATE TABLE members;"},
    },
    "api_spec": {"artifact_type": "api_spec", "content": {"endpoints": []}},
}

GOOD: dict[str, Any] = {
    "hld": {
        "title": "High-Level Design — FitPulse",
        "system_overview": "FitPulse schedules gym classes for its members.",
        "components": [
            {"name": "Scheduler", "technology": "FastAPI", "description": "Books classes"}
        ],
        "architecture_pattern": "Modular monolith",
    },
    "lld": {
        "title": "Low-Level Design — FitPulse",
        "modules": [
            {"name": "members", "endpoints": [{"method": "GET", "path": "/api/v1/members"}]}
        ],
    },
    "roadmap": {
        "title": "Sprint Roadmap — FitPulse",
        "phases": [{"name": "Phase 1: Members", "duration": "2 weeks", "deliverables": ["CRUD"]}],
        "total_duration": "6 weeks",
    },
}


@pytest.mark.asyncio
async def test_enrichment_replaces_architecture_documents(monkeypatch: pytest.MonkeyPatchPatch):
    """A spec-grounded response replaces HLD/LLD/roadmap but nothing else."""
    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", _fake_create)
    monkeypatch.setattr(arch_enricher.mvp_builder, "send_message", _fake_send(GOOD))
    monkeypatch.setattr(arch_enricher.mvp_builder, "abort_session", _fake_abort)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    assert result["hld"]["content"] == GOOD["hld"]
    assert "FitPulse schedules gym classes" in result["hld"]["content_text"]
    assert result["lld"]["content"] == GOOD["lld"]
    assert result["roadmap"]["content"]["total_duration"] == "6 weeks"
    # artifact_type is preserved for the UI even though content was replaced.
    assert result["hld"]["artifact_type"] == "hld"
    assert result["roadmap"]["artifact_type"] == "roadmap"


@pytest.mark.asyncio
async def test_structured_artifacts_are_untouched(monkeypatch: pytest.MonkeyPatchPatch):
    """ER, schema and API spec come from the spec, never from the LLM."""
    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", _fake_create)
    monkeypatch.setattr(arch_enricher.mvp_builder, "send_message", _fake_send(GOOD))
    monkeypatch.setattr(arch_enricher.mvp_builder, "abort_session", _fake_abort)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    for key in ("er_diagram", "database_schema", "api_spec", "industry"):
        assert result[key] == BASE[key]


@pytest.mark.asyncio
async def test_sidecar_failure_falls_back_to_deterministic(monkeypatch: pytest.MonkeyPatchPatch):
    """Any sidecar error must return the deterministic artifacts unchanged."""

    async def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("sidecar unreachable")

    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", boom)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    assert result == BASE


@pytest.mark.asyncio
async def test_malformed_json_falls_back(monkeypatch: pytest.MonkeyPatchPatch):
    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", _fake_create)
    monkeypatch.setattr(
        arch_enricher.mvp_builder,
        "send_message",
        _fake_send({"parts": [{"type": "text", "text": "not json at all"}]}),
    )
    monkeypatch.setattr(arch_enricher.mvp_builder, "abort_session", _fake_abort)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    assert result == BASE


@pytest.mark.asyncio
async def test_partial_response_keeps_untouched_sections(monkeypatch: pytest.MonkeyPatchPatch):
    """Only the sections the model actually returned may change."""
    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", _fake_create)
    monkeypatch.setattr(arch_enricher.mvp_builder, "send_message", _fake_send({"hld": GOOD["hld"]}))
    monkeypatch.setattr(arch_enricher.mvp_builder, "abort_session", _fake_abort)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    assert result["hld"]["content"] == GOOD["hld"]
    assert result["lld"] == BASE["lld"]
    assert result["roadmap"] == BASE["roadmap"]


@pytest.mark.asyncio
async def test_disabled_by_configuration(monkeypatch: pytest.MonkeyPatchPatch):
    called = False

    async def spy(*args: Any, **kwargs: Any) -> Any:
        nonlocal called
        called = True
        return "ses"

    monkeypatch.setattr(arch_enricher.settings, "OPENCODE_ARCH_ENRICH", False)
    monkeypatch.setattr(arch_enricher.mvp_builder, "create_session", spy)

    result = await enrich_architecture(BASE, SPEC, "FitPulse", "fitness_gym")

    assert result == BASE
    assert called is False


def test_spec_summary_mentions_real_entities_and_actions() -> None:
    """The prompt must carry the app's real nouns so the model cannot be generic."""
    text = arch_enricher._spec_summary(SPEC, "FitPulse", "fitness_gym")

    for needle in ("FitPulse", "members", "classes", "class_occupancy", "Manage members"):
        assert needle in text, needle


def test_render_emits_no_placeholders() -> None:
    text = arch_enricher._render("hld", GOOD["hld"])
    assert "Scheduler" in text
    for placeholder in ("TBD", "lorem", "<", "TODO", "None"):
        assert placeholder not in text


async def _fake_create(title: str = "", seed: str = "") -> str:
    return "ses_test"


async def _fake_abort(session_id: str, **kwargs: Any) -> None:
    return None


def _fake_send(payload: Any):
    """Wrap ``payload`` in the sidecar's real message shape: {"parts":[{"type":"text",...}]}.

    A plain dict is serialized to JSON text; a dict that already looks like a
    sidecar response (has ``parts``) is passed through untouched.
    """
    import json

    if isinstance(payload, dict) and "parts" in payload:
        body: Any = payload
    else:
        body = {"parts": [{"type": "text", "text": json.dumps(payload)}]}

    async def _send(session_id: str, text: str, **kwargs: Any) -> Any:
        return body

    return _send
