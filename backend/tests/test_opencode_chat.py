"""Integration tests for the OpenCode direct chat endpoint.

The OpenCode sidecar is mocked. The ``build_requested`` finalize path runs the
real bundled MVP scaffold through the real verifier, so the test is meaningful
without needing npm or a live sidecar.
"""

from pathlib import Path

from app.core.config import settings


def _patch_sidecar(monkeypatch, response_text="I added the inventory API."):
    """Patch the sidecar client fns used by the chat endpoint."""
    created = {"count": 0}

    async def _health():
        return True

    async def _create(title):
        created["count"] += 1
        return "sess-abc"

    async def _send(session_id, text, **kwargs):
        return {
            "id": "msg-1",
            "info": {"error": None},
            "parts": [{"type": "text", "text": response_text}],
        }

    monkeypatch.setattr("app.api.opencode_chat.builder.health", _health)
    monkeypatch.setattr("app.api.opencode_chat.builder.create_session", _create)
    monkeypatch.setattr("app.api.opencode_chat.builder.send_message", _send)
    return created


async def test_health_reports_sidecar_down_but_service_healthy(auth_client, monkeypatch):
    """When the sidecar is offline the service is still healthy (via the
    integrated synthesizer).  ``sidecar_healthy`` accurately reports False."""
    client = auth_client["client"]

    async def _no():
        return False

    monkeypatch.setattr("app.api.opencode_chat.builder.health", _no)
    resp = await client.get("/api/v1/opencode/health", headers=auth_client["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["sidecar_healthy"] is False
    assert body["mode"] == "integrated-synthesizer"


async def test_health_reports_healthy(auth_client, monkeypatch):
    client = auth_client["client"]

    async def _yes():
        return True

    monkeypatch.setattr("app.api.opencode_chat.builder.health", _yes)
    resp = await client.get("/api/v1/opencode/health", headers=auth_client["headers"])
    assert resp.status_code == 200
    assert resp.json()["healthy"] is True


async def test_chat_falls_back_to_synthesizer_when_sidecar_down(auth_client, monkeypatch):
    """When the sidecar is offline the chat endpoint falls back to the
    integrated synthesizer (direct LLM) instead of emitting an error."""
    client = auth_client["client"]
    headers = auth_client["headers"]

    async def _no():
        return False

    monkeypatch.setattr("app.api.opencode_chat.builder.health", _no)

    # Mock the LLM so we don't need real credentials in CI.
    class _FakeResponse:
        content = "I've outlined the inventory module for your app."

    class _FakeLLM:
        async def ainvoke(self, messages, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr("app.api.opencode_chat.get_llm", lambda: _FakeLLM())

    resp = await client.post("/api/v1/opencode/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200, resp.text
    # Should NOT contain an error event.
    assert "event: error" not in resp.text
    # Should contain a successful reply from the synthesizer fallback.
    assert '"agent": "AI Developer"' in resp.text
    assert "I've outlined the inventory module" in resp.text


async def test_chat_synthesizer_with_mock_llm_returns_rich_content_not_raw_json(
    auth_client, monkeypatch
):
    """When sidecar is down and real LLM is not configured (MockChatModel used),
    the endpoint returns clean, rich markdown text, never raw '{"content": "Mock response"}'.
    """
    client = auth_client["client"]
    headers = auth_client["headers"]

    async def _no():
        return False

    monkeypatch.setattr("app.api.opencode_chat.builder.health", _no)
    monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "mock")

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "I want to build an inventory and retail management app"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "Mock response" not in resp.text
    assert "Retail & Inventory" in resp.text or "Data Models" in resp.text
    assert '"content": "Mock response"' not in resp.text


async def test_chat_reuses_persisted_session(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    created = _patch_sidecar(monkeypatch)

    # Scaffold into a stable temp dir listing a tiny placeholder so the
    # "already scaffolded" guard short-circuits on subsequent turns.
    workdir = Path(settings.MVP_BUILD_DIR) / f"chat-test-{solution_id[:8]}"

    def _chat_workspace_dir(sid):
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir

    def _scaffold(build_dir, *, app_title, inject_modules, **kwargs):
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "placeholder.txt").write_text("scaffolded", encoding="utf-8")

    monkeypatch.setattr("app.api.opencode_chat.builder.chat_workspace_dir", _chat_workspace_dir)
    monkeypatch.setattr("app.api.opencode_chat.builder.scaffold_build", _scaffold)

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "add inventory", "solution_id": solution_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert '"session_id": "sess-abc"' in resp.text
    assert "I added the inventory API." in resp.text
    assert created["count"] == 1

    # Second call reuses the persisted session -> no new session created.
    resp2 = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "add orders", "solution_id": solution_id},
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert '"session_id": "sess-abc"' in resp2.text
    assert created["count"] == 1


async def test_chat_build_requested_finalizes_build(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    _patch_sidecar(monkeypatch)  # real scaffold + real verifier

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "build my app", "solution_id": solution_id, "build_requested": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "event: complete" in resp.text
    assert '"status": "complete"' in resp.text
    assert '"build_id"' in resp.text
    assert '"file_count"' in resp.text

    sol_resp = await client.get(f"/api/v1/solutions/{solution_id}", headers=headers)
    assert sol_resp.status_code == 200
    assert sol_resp.json()["status"] == "complete"
    assert len(sol_resp.json().get("artifacts") or []) > 0


async def test_chat_rejects_session_id_mismatch(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    created = _patch_sidecar(monkeypatch)

    workdir = Path(settings.MVP_BUILD_DIR) / f"chat-mismatch-{solution_id[:8]}"

    def _chat_workspace_dir(sid):
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir

    def _scaffold(build_dir, *, app_title, inject_modules, **kwargs):
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "placeholder.txt").write_text("scaffolded", encoding="utf-8")

    monkeypatch.setattr("app.api.opencode_chat.builder.chat_workspace_dir", _chat_workspace_dir)
    monkeypatch.setattr("app.api.opencode_chat.builder.scaffold_build", _scaffold)

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "add inventory", "solution_id": solution_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Client sends a session_id that does not match the persisted one.
    resp2 = await client.post(
        "/api/v1/opencode/chat",
        json={
            "message": "add orders",
            "solution_id": solution_id,
            "session_id": "other-sess",
        },
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert "event: error" in resp2.text
    assert "Session id does not match this solution." in resp2.text
    assert created["count"] == 1


async def test_chat_includes_uploaded_context(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    _patch_sidecar(monkeypatch, response_text="I saw your notes.")

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={
            "message": "add invoicing",
            "solution_id": solution_id,
            "uploaded_context": "Requirement notes: 30-day payment terms.",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "I saw your notes." in resp.text


async def test_chat_verification_failure_emits_error(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    _patch_sidecar(monkeypatch)

    from app.services import mvp_verifier as verifier_mod

    async def _raise_verification_error(*args, **kwargs):
        raise verifier_mod.VerificationError("broken backend structure")

    monkeypatch.setattr(
        "app.api.opencode_chat.mvp_verifier.verify_and_repair", _raise_verification_error
    )

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={
            "message": "build my app",
            "solution_id": solution_id,
            "build_requested": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "event: error" in resp.text
    assert "Build verification failed" in resp.text


async def test_chat_auto_creates_solution_when_missing(auth_client, monkeypatch):
    client = auth_client["client"]
    headers = auth_client["headers"]

    _patch_sidecar(monkeypatch)

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "make a crm", "app_name": "MyCRM"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert '"session_id": "sess-abc"' in resp.text
    assert '"solution_id"' in resp.text


async def test_chat_cannot_access_other_users_solution(workspace_solution, monkeypatch):
    client = workspace_solution["client"]

    _patch_sidecar(monkeypatch)
    from uuid import uuid4

    other_email = f"chat-intruder-{uuid4().hex[:8]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": other_email,
            "full_name": "Chat Intruder",
            "password": "Testpass123!",
            "org_name": "Intruder-Org",
        },
    )
    assert reg.status_code == 201, reg.text
    intruder_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={"message": "steal", "solution_id": workspace_solution["solution_id"]},
        headers=intruder_headers,
    )
    assert resp.status_code == 404


def test_synthesize_domain_artifacts_ai_agents():
    from app.api.opencode_chat import _synthesize_domain_artifacts

    artifacts = _synthesize_domain_artifacts(
        "AI Agent App", "Build an autonomous AI agent with tool calling and memory"
    )
    assert artifacts["industry"] == "ai_agents"
    assert "agent_orchestration" in artifacts["confirmed_modules"]
    assert "tool_registry" in artifacts["confirmed_modules"]

    entities = artifacts["er_diagram"]["content"]["entities"]
    entity_names = [e["name"] for e in entities]
    assert "agents" in entity_names
    assert "tools" in entity_names
    assert "conversations" in entity_names
    assert "messages" in entity_names
    assert "executions" in entity_names

    agent_entity = next(e for e in entities if e["name"] == "agents")
    agent_field_names = [f["name"] for f in agent_entity["fields"]]
    assert "system_prompt" in agent_field_names
    assert "temperature" in agent_field_names
    assert "model" in agent_field_names


async def test_chat_ai_agent_request_builds_agent_architecture(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    _patch_sidecar(monkeypatch)

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={
            "message": "Create an autonomous AI agent with tool calling capabilities",
            "solution_id": solution_id,
            "build_requested": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "event: build_progress" in resp.text
    assert "event: complete" in resp.text

    sol_resp = await client.get(f"/api/v1/solutions/{solution_id}", headers=headers)
    assert sol_resp.status_code == 200
    sol_data = sol_resp.json()
    assert sol_data["status"] == "complete"
    assert sol_data["ai_state"]["industry"] == "ai_agents"
    assert "agent_orchestration" in sol_data["ai_state"]["confirmed_modules"]


async def test_chat_build_requested_emits_granular_progress_events(workspace_solution, monkeypatch):
    """When build_requested is True, SSE stream yields granular build_progress events."""
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    _patch_sidecar(monkeypatch)

    resp = await client.post(
        "/api/v1/opencode/chat",
        json={
            "message": "Finalize and generate MVP artifacts",
            "solution_id": solution_id,
            "build_requested": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "event: build_progress" in resp.text
    assert '"phase": "analyzing"' in resp.text
    assert '"phase": "scaffolding"' in resp.text
    assert '"phase": "completed"' in resp.text
    assert "event: complete" in resp.text


def test_synthesize_domain_artifacts_no_false_positive_ai_matches():
    """Words containing 'ai' (retail, trainer, email, repair) must NOT trigger ai_agents."""
    from app.api.opencode_chat import _synthesize_domain_artifacts

    prompts = [
        "Build a retail clothing store management app",
        "Personal trainer and fitness workout tracker",
        "Email marketing campaign manager",
        "Auto repair and maintenance shop booking",
    ]
    for p in prompts:
        artifacts = _synthesize_domain_artifacts("Test App", p)
        assert artifacts["industry"] != "ai_agents", f"Prompt '{p}' incorrectly matched ai_agents!"


def test_extract_app_title():
    """Verify clean title extraction from user prompts."""
    from app.api.opencode_chat import _extract_app_title

    assert _extract_app_title("Build a gym management platform called IronFit") == "IronFit"
    assert _extract_app_title("Create an app named PetHaven for pet adoption") == "PetHaven"
    assert _extract_app_title("Build an app for hotel booking") == "Hotel Booking"
    assert _extract_app_title("Build a restaurant food ordering system") == "Restaurant Food Ordering System"
    assert _extract_app_title("hello") == "Custom App"


def test_synthesize_domain_artifacts_gym_fitness():
    """Verify gym/fitness domain produces fitness-specific entities."""
    from app.api.opencode_chat import _synthesize_domain_artifacts

    artifacts = _synthesize_domain_artifacts(
        "FitPulse Gym", "Build a gym and fitness club management app with members, trainers, and classes"
    )
    assert artifacts["industry"] in ("fitness", "gym_management")
    entities = artifacts["er_diagram"]["content"]["entities"]
    entity_names = [e["name"] for e in entities]
    assert "members" in entity_names
    assert "trainers" in entity_names
    assert "workouts" in entity_names or "classes" in entity_names or "subscriptions" in entity_names


def test_synthesize_domain_artifacts_restaurant():
    """Verify restaurant domain produces food & beverage entities."""
    from app.api.opencode_chat import _synthesize_domain_artifacts

    artifacts = _synthesize_domain_artifacts(
        "Bistro Cafe", "Create a restaurant food ordering and table reservation platform"
    )
    assert artifacts["industry"] == "food_and_beverage"
    entities = artifacts["er_diagram"]["content"]["entities"]
    entity_names = [e["name"] for e in entities]
    assert "menus" in entity_names or "menu_items" in entity_names
    assert "dishes" in entity_names or "orders" in entity_names


async def test_synthesize_domain_artifacts_dynamic_preserves_state():
    """When the user provides a short confirmation prompt ('build it'), existing domain state is preserved."""
    from app.api.opencode_chat import _synthesize_domain_artifacts_dynamic

    existing_state = {
        "industry": "fitness",
        "confirmed_modules": ["members", "trainers"],
        "er_diagram": {
            "type": "er_diagram",
            "content": {
                "entities": [
                    {"name": "members", "fields": [{"name": "id", "type": "uuid"}]},
                    {"name": "trainers", "fields": [{"name": "id", "type": "uuid"}]},
                ]
            }
        },
    }

    result = await _synthesize_domain_artifacts_dynamic("FitPulse", "build it now", existing_state=existing_state)
    assert result["industry"] == "fitness"
    entity_names = [e["name"] for e in result["er_diagram"]["content"]["entities"]]
    assert "members" in entity_names
    assert "trainers" in entity_names

