"""Unit and integration tests covering Phases P1 through P6:

P1: Requirement Gap Agent, Feature Advisor Agent, Decisions API, Artifact Explain API
P2: Artifact DAG service, Solution Approval Gate, Request Changes, Cascading Regenerate, UI Theme
P3: Multilingual/Audio/Image/System upload endpoints and i18n utilities
P4: Vercel Deployer, Deployment Orchestrator, MVP Rollback endpoint
P5 & P6: RBAC permissions and Monetization Quote/Checkout endpoints
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.nodes.feature_advisor import feature_advisor_node
from app.agents.nodes.requirement_gap import requirement_gap_node
from app.core.i18n import detect_language, is_rtl
from app.models.artifact import SolutionArtifact
from app.services.artifact_graph import get_direct_downstream, get_downstream
from app.services.deploy_orchestrator import DeploymentOrchestrator
from app.services.vercel_deployer import VercelDeployer


# ── P1: Requirement Intelligence & Explainability Tests ─────────────────────
@pytest.mark.asyncio
async def test_requirement_gap_node():
    state = {
        "solution_title": "Omnichannel CRM",
        "industry": "retail",
        "business_description": "Store chain needing inventory sync",
        "user_message": "Build a CRM for our 10 retail outlets",
        "requirements": [],
        "open_questions": [],
    }
    with patch("app.agents.nodes.requirement_gap.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value.content = (
            '{"open_questions": ["What is your current ERP?"], '
            '"assumptions_log": [{"topic": "Cloud", "assumption": "AWS cloud preferred"}], '
            '"ambiguities": ["Offline support needed?"]}'
        )
        mock_get_llm.return_value = mock_llm

        res = await requirement_gap_node(state)
        assert len(res["open_questions"]) >= 1
        assert "What is your current ERP?" in res["open_questions"]
        assert len(res["assumptions_log"]) >= 1


@pytest.mark.asyncio
async def test_feature_advisor_node():
    state = {
        "industry": "healthcare",
        "business_description": "Clinic management software",
        "user_message": "Need scheduling and billing",
        "suggested_features": [],
    }
    with patch("app.agents.nodes.feature_advisor.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value.content = (
            '{"suggested_features": [{"id": "f1", "name": "Telehealth Video Visits", '
            '"description": "HIPAA-compliant video consults", '
            '"competitive_benchmark": "90% of modern clinics offer telehealth", '
            '"roi_rationale": "Reduces clinic overhead by 30%", '
            '"complexity": "medium", "category": "experience"}]}'
        )
        mock_get_llm.return_value = mock_llm

        res = await feature_advisor_node(state)
        assert len(res["suggested_features"]) >= 1
        assert res["suggested_features"][0]["name"] == "Telehealth Video Visits"


@pytest.mark.asyncio
async def test_decisions_and_explain_endpoints(auth_client, session_factory):
    client = auth_client["client"]
    headers = auth_client["headers"]

    # 1. Create a solution
    ws_res = await client.get("/api/v1/workspaces/", headers=headers)
    assert ws_res.status_code == 200
    workspaces = ws_res.json()
    ws_id = workspaces[0]["id"] if workspaces else None
    if not ws_id:
        ws_post = await client.post(
            "/api/v1/workspaces/", json={"name": "P1 Workspace"}, headers=headers
        )
        ws_id = ws_post.json()["id"]

    sol_resp = await client.post(
        "/api/v1/solutions/",
        json={"workspace_id": ws_id, "title": "Explainable Solution"},
        headers=headers,
    )
    assert sol_resp.status_code == 201
    sol_id = sol_resp.json()["id"]

    # 2. Add an artifact with decisions and evidence
    async with session_factory() as session:
        art = SolutionArtifact(
            solution_id=uuid.UUID(sol_id),
            artifact_type="hld",
            title="System Architecture Blueprint",
            content={
                "decisions": [
                    {
                        "id": "dec-1",
                        "title": "Use PostgreSQL with pgvector",
                        "rationale": "Unified relational and semantic similarity search",
                        "tradeoffs": "Requires dedicated extension",
                    }
                ],
                "evidence": [
                    {
                        "source": "Requirement 1",
                        "excerpt": "Must search through customer notes quickly",
                    }
                ],
            },
            content_text="HLD document with architecture details",
            version=1,
        )
        session.add(art)
        await session.commit()
        await session.refresh(art)
        art_id = str(art.id)

    # 3. Test GET /solutions/{id}/decisions
    dec_res = await client.get(f"/api/v1/solutions/{sol_id}/decisions", headers=headers)
    assert dec_res.status_code == 200
    dec_json = dec_res.json()
    assert dec_json["total_decisions"] >= 1
    assert dec_json["decisions"][0]["title"] == "Use PostgreSQL with pgvector"

    # 4. Test GET /artifacts/{id}/explain
    exp_res = await client.get(f"/api/v1/artifacts/{art_id}/explain", headers=headers)
    assert exp_res.status_code == 200
    exp_json = exp_res.json()
    assert len(exp_json["decisions"]) == 1
    assert len(exp_json["evidence"]) == 1


# ── P2: Blueprint Approval Gate & DAG Tests ─────────────────────────────────
def test_artifact_dag_traversal():
    # Direct downstream
    assert get_direct_downstream("requirements") == ["hld", "wireframe", "bpmn"]
    assert get_direct_downstream("database_schema") == ["api_spec"]

    # Transitive downstream
    req_downstream = get_downstream("requirements")
    assert "hld" in req_downstream
    assert "lld" in req_downstream
    assert "er_diagram" in req_downstream
    assert "code" in req_downstream


@pytest.mark.asyncio
async def test_solution_approval_and_theme_endpoints(auth_client, session_factory):
    client = auth_client["client"]
    headers = auth_client["headers"]

    # Fetch/create workspace
    ws_res = await client.get("/api/v1/workspaces/", headers=headers)
    assert ws_res.status_code == 200
    workspaces = ws_res.json()
    ws_id = workspaces[0]["id"] if workspaces else None
    if not ws_id:
        ws_post = await client.post(
            "/api/v1/workspaces/", json={"name": "Approval Workspace"}, headers=headers
        )
        ws_id = ws_post.json()["id"]

    # Create solution
    sol_resp = await client.post(
        "/api/v1/solutions/",
        json={"workspace_id": ws_id, "title": "Approval Pipeline Solution"},
        headers=headers,
    )
    sol_id = sol_resp.json()["id"]

    # Create an artifact
    async with session_factory() as session:
        art = SolutionArtifact(
            solution_id=uuid.UUID(sol_id),
            artifact_type="requirements",
            title="PRD v1",
            content={"summary": "v1 requirements"},
            content_text="v1 PRD text",
            version=1,
        )
        session.add(art)
        await session.commit()

    # 1. Approve blueprint
    app_res = await client.post(
        f"/api/v1/solutions/{sol_id}/approve",
        json={"comments": "LGTM, proceed to MVP build."},
        headers=headers,
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["approval_status"] == "approved"
    assert app_data["status"] == "approved"

    # 2. Request changes
    chg_res = await client.post(
        f"/api/v1/solutions/{sol_id}/request-changes",
        json={"comments": "Please add OAuth login flow."},
        headers=headers,
    )
    assert chg_res.status_code == 200
    chg_data = chg_res.json()
    assert chg_data["approval_status"] == "changes_requested"
    assert chg_data["status"] == "changes_requested"

    # 3. Cascading regenerate calculation
    reg_res = await client.post(
        f"/api/v1/solutions/{sol_id}/regenerate",
        json={"targets": ["requirements"], "feedback": "Updated requirements"},
        headers=headers,
    )
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert "hld" in reg_data["affected_artifacts"]
    assert reg_data["estimated_credits"] >= 2

    # 4. Customize UI Theme
    theme_res = await client.patch(
        f"/api/v1/solutions/{sol_id}/theme",
        json={"primary_color": "#6366f1", "font_family": "Inter", "border_radius": "8px"},
        headers=headers,
    )
    assert theme_res.status_code == 200
    theme_data = theme_res.json()
    assert theme_data["ui_theme"]["primary_color"] == "#6366f1"


# ── P3: File Upload & i18n Tests ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i18n_and_uploads(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    # Language detection and RTL
    assert detect_language("નમસ્તે તમે કેમ છો") == "gu"
    assert detect_language("नमस्ते आप कैसे हैं") == "hi"
    assert detect_language("Hello world, this is a test.") == "en"
    assert is_rtl("ar") is True
    assert is_rtl("he") is True
    assert is_rtl("en") is False

    # Audio upload endpoint
    audio_content = b"RIFF....WAVEfmt ...."
    files = {"file": ("test_note.wav", audio_content, "audio/wav")}
    aud_res = await client.post("/api/v1/upload/audio", files=files, headers=headers)
    assert aud_res.status_code == 200
    aud_json = aud_res.json()
    assert aud_json["filename"] == "test_note.wav"
    assert "transcription" in aud_json

    # Image upload endpoint
    img_content = b"\x89PNG\r\n\x1a\nfake_image_bytes"
    files = {"file": ("dashboard_mockup.png", img_content, "image/png")}
    img_res = await client.post("/api/v1/upload/image", files=files, headers=headers)
    assert img_res.status_code == 200
    img_json = img_res.json()
    assert "extracted_context" in img_json

    # System import endpoint
    sys_res = await client.post(
        "/api/v1/upload/system",
        json={"sop_text": "Step 1: Order received. Step 2: Notify inventory."},
        headers=headers,
    )
    assert sys_res.status_code == 200
    sys_json = sys_res.json()
    assert "Step 1: Order received" in sys_json["extracted_context"]


# ── P4: Deployment Orchestration Tests ──────────────────────────────────────
@pytest.mark.asyncio
async def test_vercel_and_deployment_orchestrator():
    vercel = VercelDeployer(token="test_vercel_token")
    assert vercel.token == "test_vercel_token"

    orchestrator = DeploymentOrchestrator(
        github_token="ghp_test_token",
        render_api_key="rnd_test_key",
        vercel_token="vcl_test_token",
    )

    with (
        patch("app.services.render_deployer.RenderDeployer.deploy_repo") as mock_render,
        patch("app.services.vercel_deployer.VercelDeployer.create_or_get_project") as mock_vc_proj,
        patch("app.services.vercel_deployer.VercelDeployer.trigger_deployment") as mock_vc_deploy,
    ):
        mock_render.return_value = {
            "backend_url": "https://test-proj-backend.onrender.com",
            "service_id": "srv-123",
        }
        mock_vc_proj.return_value = {"id": "prj-456", "name": "test-proj"}
        mock_vc_deploy.return_value = {
            "id": "dpl-789",
            "url": "https://test-proj.vercel.app",
            "readyState": "READY",
        }

        dep_result = await orchestrator.orchestrate_deployment(
            project_name="test-solution",
            github_repo="https://github.com/org/test-repo",
            git_branch="main",
        )

        assert dep_result["status"] == "live"
        assert "urls" in dep_result
        assert "events" in dep_result
        assert len(dep_result["verification_checks"]) >= 3

    rollback_result = await orchestrator.rollback_deployment(
        deployment_id="dep-123", target_commit_sha="a1b2c3d4e5f6"
    )
    assert rollback_result["status"] == "rolled_back"


# ── P5 & P6: RBAC & Monetization Tests ──────────────────────────────────────
@pytest.mark.asyncio
async def test_billing_quote_and_checkout(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    # GET /billing/quote
    q_res = await client.get(
        "/api/v1/billing/quote?action=mvp_build&target_count=1", headers=headers
    )
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["credits_required"] == 25
    assert q_data["action"] == "mvp_build"

    # POST /billing/checkout with simulated pack
    chk_res = await client.post(
        "/api/v1/billing/checkout",
        json={"pack_credits": 100, "gateway": "razorpay", "currency": "INR"},
        headers=headers,
    )
    assert chk_res.status_code == 200
    chk_data = chk_res.json()
    assert chk_data["gateway"] == "razorpay"
    assert "amount" in chk_data
    assert "order_id" in chk_data
