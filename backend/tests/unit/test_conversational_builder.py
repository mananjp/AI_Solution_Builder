"""
Regression tests for the three failures that made builds come out static:

  1. Generated apps shipped a fake data layer (in-memory store, another app's
     sample rows, action handlers that echoed output_example).
  2. Action stubs returned the very value the acceptance test asserted, so the
     suite passed against an app that computed nothing.
  3. Nothing the user read was written in plain language, and nothing ever
     asked them a question.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.services.app_spec import AppSpec
from app.services.build_conversation import (
    ConversationState,
    Stage,
    TurnResult,
    _is_approval,
    handle_turn,
    is_answerable_by_layman,
    record_answers,
)
from app.services.fake_detector import audit_build, blockers, detect_constant_actions
from app.services.mvp_builder import template_root
from app.services.plain_language import (
    describe_change,
    describe_data_loss,
    describe_progress,
    describe_spec,
    describe_test_results,
    dejargon,
    lint_for_jargon,
)
from app.services.real_backend_codegen import enforce_distinguishing_tests
from app.services import spec_codegen

FIXTURE = Path(__file__).parent / "fixtures" / "cyclefix_spec.json"


@pytest.fixture
def spec() -> AppSpec:
    return AppSpec.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture
def workspace(tmp_path: Path, spec: AppSpec) -> Path:
    root = tmp_path / "app"
    shutil.copytree(template_root(), root)
    spec_codegen.write_generated(root, spec)
    return root


# ── 1. The generated app must have a real data layer ────────────────────


def test_no_in_memory_store_is_generated(workspace: Path):
    """The ice-cream DataStore must not exist in any generated app."""
    assert not (workspace / "frontend" / "src" / "lib" / "db.ts").exists()
    sources = list(workspace.rglob("*.ts")) + list(workspace.rglob("*.tsx"))
    joined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources).lower()
    assert "madagascar vanilla" not in joined
    assert "sarah jenkins" not in joined
    assert "private tables" not in joined


def test_api_calls_reach_a_real_server(workspace: Path):
    """/api/v1 must proxy to the application server, not answer locally."""
    proxy = workspace / "frontend" / "src" / "app" / "api" / "v1" / "[...path]" / "route.ts"
    assert proxy.exists(), "catch-all proxy route is missing"
    body = proxy.read_text()
    assert "BACKEND" in body and "fetch(" in body
    # No per-entity handler may shadow the proxy with canned data.
    others = [
        p
        for p in (workspace / "frontend" / "src" / "app" / "api").rglob("route.ts")
        if p != proxy
    ]
    assert others == [], f"fake route handlers still generated: {others}"


def test_audit_catches_a_fake_data_layer(workspace: Path, spec: AppSpec):
    """Re-introducing the old fake layer must be reported as a blocker."""
    db = workspace / "frontend" / "src" / "lib" / "db.ts"
    db.write_text(
        "class DataStore { private tables = new Map(); list(t){return []} insert(){} }\n"
        'const seed = [{ name: "Classic Madagascar Vanilla" }];\n',
        encoding="utf-8",
    )
    found = blockers(audit_build(workspace, spec))
    reasons = " ".join(f.detail for f in found)
    assert "In-memory store" in reasons
    assert "madagascar vanilla" in reasons.lower()


# ── 2. The test gate must not be self-confirming ────────────────────────


def test_action_stub_fails_instead_of_faking(workspace: Path):
    """A stub must raise 501, never return the expected example value."""
    actions = (workspace / "backend" / "actions.py").read_text()
    assert "501" in actions
    assert "'total': 1200" not in actions and '"total": 1200' not in actions


def test_constant_action_is_a_blocker(workspace: Path, spec: AppSpec):
    """An action that returns a literal without reading data is fake."""
    actions = workspace / "backend" / "actions.py"
    body = actions.read_text()
    start = body.index("async def quote")
    head = body[:start]
    actions.write_text(
        head
        + "async def quote(repair_id: int, session: SessionDep) -> dict[str, Any]:\n"
        + '    return {"total": 1200, "labour": 800, "parts": 400}\n',
        encoding="utf-8",
    )
    found = detect_constant_actions(workspace, spec)
    assert found, "a constant-returning action was not detected"
    assert "always gives the same answer" in found[0].what


def test_real_implementation_passes_audit(workspace: Path, spec: AppSpec):
    """Reading from the database and computing clears the gate."""
    actions = workspace / "backend" / "actions.py"
    body = actions.read_text()
    start = body.index("async def quote")
    actions.write_text(
        body[:start]
        + "async def quote(repair_id: int, session: SessionDep) -> dict[str, Any]:\n"
        "    repair = await session.get(models.Repair, repair_id)\n"
        '    if repair is None:\n        raise HTTPException(404, "repair not found")\n'
        "    labour = float(repair.labour_hours or 0) * 400\n"
        "    parts = float(repair.parts_cost or 0)\n"
        '    return {"total": parts + labour, "labour": labour, "parts": parts}\n',
        encoding="utf-8",
    )
    assert detect_constant_actions(workspace, spec) == []


def test_each_action_has_distinguishing_scenarios(spec: AppSpec):
    """Two differing scenarios per action, so a constant cannot pass."""
    assert enforce_distinguishing_tests(spec) == []


def test_single_scenario_action_is_flagged(spec: AppSpec):
    """One scenario is not enough to prove an action works."""
    data = spec.model_dump()
    # Point the 404 scenario at a different action path, leaving the quote
    # action with a single scenario that a hardcoded value would satisfy.
    for test in data["acceptance_tests"]:
        if test["name"] == "missing_repair":
            test["steps"][0]["path"] = "/repairs/999"
    weakened = AppSpec.model_validate(data)
    problems = enforce_distinguishing_tests(weakened)
    assert problems and "fixed answer" in problems[0]


# ── 3. Plain language ───────────────────────────────────────────────────


def test_plan_has_no_developer_jargon(spec: AppSpec):
    """What the user approves must be readable by a shop owner."""
    plan = describe_spec(spec)
    hits = [h.term.lower() for h in lint_for_jargon(plan)]
    assert hits == [], f"jargon reached the user: {hits}"


def test_plan_describes_what_the_app_does(spec: AppSpec):
    plan = describe_spec(spec)
    assert "CycleFix" in plan
    assert "What it will remember" in plan
    assert "labour hours" in plan or "labour" in plan
    assert "{" not in plan and "/api" not in plan


def test_dejargon_replaces_known_terms():
    assert "connection" in dejargon("The API is ready").lower()
    assert "kinds of information" in dejargon("Define your entities").lower()
    assert dejargon("Deploy the backend").startswith("Put online")


def test_progress_is_human_readable():
    assert describe_progress("scaffolding") == "Setting up the basic structure"
    assert "customer" in describe_progress("verifying").lower()
    assert describe_test_results(6, 0).startswith("I ran 6 real check")
    assert "fixing" in describe_test_results(4, 2)


def test_changes_are_described_in_business_terms(spec: AppSpec):
    data = spec.model_dump()
    data["entities"][1]["fields"].append(
        {"name": "discount", "type": "float", "required": False}
    )
    updated = AppSpec.model_validate(data)
    changes = describe_change(spec, updated)
    assert any("discount" in c for c in changes)
    assert all("field" not in c.lower() for c in changes)


def test_removing_a_field_warns_about_lost_data(spec: AppSpec):
    data = spec.model_dump()
    data["entities"][1]["fields"] = [
        f for f in data["entities"][1]["fields"] if f["name"] != "parts_cost"
    ]
    reduced = AppSpec.model_validate(data)
    warnings = describe_data_loss(spec, reduced)
    assert warnings and "will be lost" in warnings[0]


# ── 4. The conversation ─────────────────────────────────────────────────


def test_developer_questions_are_rejected():
    assert not is_answerable_by_layman("Which database should we use?")
    assert not is_answerable_by_layman("Do you want REST or GraphQL?")
    assert not is_answerable_by_layman("Should I deploy this to Vercel?")
    assert is_answerable_by_layman("Do you charge by the hour or a flat fee?")
    assert is_answerable_by_layman("What should happen if two people book the same slot?")


def test_approval_detection():
    for yes in ("yes", "go ahead", "build it", "looks good", "haan", "theek hai"):
        assert _is_approval(yes), yes
    for no in ("no wait", "change the colours please", "what about refunds?"):
        assert not _is_approval(no), no


def test_answers_are_recorded_against_questions():
    from app.services.build_conversation import Question

    state = ConversationState(
        questions=[Question(id="q1", question="Flat fee or hourly?", why="changes the bill")]
    )
    record_answers(state, {"q1": "hourly, 400 rupees"})
    assert state.answered()[0].answer == "hourly, 400 rupees"
    assert state.pending() == []


@pytest.mark.asyncio
async def test_approved_plan_goes_straight_to_build(spec: AppSpec, monkeypatch):
    """Saying 'build it' must start a build without another model call."""

    async def _boom(*args, **kwargs):  # pragma: no cover
        raise AssertionError("the model should not be called to approve a plan")

    monkeypatch.setattr("app.services.build_conversation._call_model", _boom)
    state = ConversationState(stage=Stage.PLAN_REVIEW, spec=spec.model_dump())
    result = await handle_turn(state, "yes build it")
    assert result.kind == "build"
    assert result.state.stage == Stage.BUILDING
    assert result.spec.app_name == "CycleFix"


@pytest.mark.asyncio
async def test_agent_asks_before_building(monkeypatch):
    """A vague request produces plain questions, not a build."""

    async def _fake_model(state, message):
        return "ask", {
            "questions": [
                {
                    "question": "Do you charge a flat fee per repair or by the hour?",
                    "why": "It changes how the bill is worked out.",
                    "options": [{"label": "Flat fee"}, {"label": "By the hour"}],
                },
                {
                    "question": "Which database would you like?",
                    "why": "Storage",
                },
            ]
        }

    monkeypatch.setattr("app.services.build_conversation._call_model", _fake_model)
    result = await handle_turn(ConversationState(), "I fix bikes, make me something")
    assert result.kind == "ask"
    assert len(result.questions) == 1, "the database question should have been dropped"
    assert "flat fee" in result.questions[0].question.lower()
    assert result.state.stage == Stage.GATHERING


@pytest.mark.asyncio
async def test_change_request_reports_plain_differences(spec: AppSpec, monkeypatch):
    """Post-build edits come back as business changes plus data warnings."""
    updated = spec.model_dump()
    updated["entities"][1]["fields"].append(
        {"name": "discount", "type": "float", "required": False}
    )

    async def _fake_model(state, message):
        return "change", {"spec": updated, "note": "I added a discount to each repair."}

    monkeypatch.setattr("app.services.build_conversation._call_model", _fake_model)
    state = ConversationState(stage=Stage.READY, spec=spec.model_dump())
    result = await handle_turn(state, "let me give regulars a discount")
    assert result.kind == "change"
    assert any("discount" in c for c in result.changes)
    assert lint_for_jargon(result.message) == []


@pytest.mark.asyncio
async def test_model_prose_becomes_an_answer_not_a_crash(monkeypatch):
    async def _fake_model(state, message):
        return "answer", {"message": "Your app stores each repair in the backend database."}

    monkeypatch.setattr("app.services.build_conversation._call_model", _fake_model)
    result = await handle_turn(ConversationState(stage=Stage.READY), "where does my data go?")
    assert result.kind == "answer"
    # Jargon in the model's reply is rewritten before the user sees it.
    assert "backend" not in result.message.lower()


def test_conversation_state_round_trips():
    from app.services.build_conversation import Question

    state = ConversationState(
        stage=Stage.PLAN_REVIEW,
        questions=[Question(id="a", question="q?", why="w", answer="yes")],
        question_rounds=2,
        spec={"app_name": "X"},
    )
    restored = ConversationState.from_dict(state.to_dict())
    assert restored.stage == Stage.PLAN_REVIEW
    assert restored.questions[0].answer == "yes"
    assert restored.question_rounds == 2


def test_landing_page_is_proper_custom_build_not_stale_template(workspace: Path, spec: AppSpec):
    """Generated landing page must overwrite the starter scaffold page and contain custom domain content."""
    page_path = workspace / "frontend" / "src" / "app" / "page.tsx"
    assert page_path.exists(), "frontend/src/app/page.tsx must exist"
    
    # Must NOT have created page.generated.tsx
    assert not (workspace / "frontend" / "src" / "app" / "page.generated.tsx").exists()

    content = page_path.read_text(encoding="utf-8")
    # Must not contain starter template placeholder strings
    assert "Autonomous MVP built by AI Solution Builder" not in content
    assert "__APP_TITLE__" not in content
    assert "@generated by AI Solution Builder" in content

    # Must contain custom domain content
    assert "CycleFix" in content or "cyclefix" in content.lower()
    assert "sarah jenkins" not in content.lower()
    assert "madagascar vanilla" not in content.lower()


def test_subsequent_build_overwrites_cleanly_without_stale_artifacts(tmp_path: Path, spec: AppSpec):
    """Subsequent build on the same workspace must cleanly overwrite and prune stale route directories."""
    root = tmp_path / "app"
    shutil.copytree(template_root(), root)
    spec_codegen.write_generated(root, spec)

    # Simulate an obsolete screen route from an earlier build
    old_route_dir = root / "frontend" / "src" / "app" / "obsolete_feature"
    old_route_dir.mkdir(parents=True, exist_ok=True)
    (old_route_dir / "page.tsx").write_text("// @generated by AI Solution Builder\nexport default function Obsolete() { return null; }")

    # Leave a stale page.generated.tsx
    stale_gen = root / "frontend" / "src" / "app" / "page.generated.tsx"
    stale_gen.write_text("// stale")

    # Now evolve spec: create a new spec without obsolete_feature
    spec_codegen.write_generated(root, spec)

    # Verify stale route dir was pruned
    assert not old_route_dir.exists()
    # Verify stale page.generated.tsx was removed
    assert not stale_gen.exists()
    # Verify no fake data or template leaks
    from app.services.fake_detector import detect_fake_data
    assert detect_fake_data(root, spec) == []

    # Provide real action implementation so full audit passes
    actions = root / "backend" / "actions.py"
    body = actions.read_text()
    start = body.index("async def quote")
    actions.write_text(
        body[:start]
        + "async def quote(repair_id: int, session: SessionDep) -> dict[str, Any]:\n"
        "    repair = await session.get(models.Repair, repair_id)\n"
        '    if repair is None:\n        raise HTTPException(404, "repair not found")\n'
        "    labour = float(repair.labour_hours or 0) * 400\n"
        "    parts = float(repair.parts_cost or 0)\n"
        '    return {"total": labour + parts, "labour": labour, "parts": parts}\n',
        encoding="utf-8",
    )
    findings = audit_build(root, spec)
    assert blockers(findings) == []

