"""
Tests for Phase P0 — Security & Correctness Fixes:
1. Gated top-up requires admin/owner (403 for member).
2. Registration assigns owner to 1st user, member to 2nd user, guest to anonymous.
3. Secret encryption at rest (including vercel_token).
4. Regeneration failure refunds credits and returns 502 without creating fake artifacts.
5. Business Analyst agent preserves assistant messages in conversation history.
"""

import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select

from app.agents.nodes.business_analyst import business_analyst_node
from app.core.secrets import decrypt_secret
from app.models.artifact import SolutionArtifact
from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_topup_requires_admin_or_owner(client: httpx.AsyncClient):
    # 1. Register first user (becomes owner of org)
    org_name = f"TopupOrg-{uuid.uuid4().hex[:6]}"
    email_owner = f"owner-{uuid.uuid4().hex[:6]}@example.com"
    r1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email_owner,
            "full_name": "Org Owner",
            "password": "Password123!",
            "org_name": org_name,
        },
    )
    assert r1.status_code == 201
    owner_headers = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    # 2. Register second user for the same org (becomes member)
    email_member = f"member-{uuid.uuid4().hex[:6]}@example.com"
    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email_member,
            "full_name": "Org Member",
            "password": "Password123!",
            "org_name": org_name,
        },
    )
    assert r2.status_code == 201
    member_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    # 3. Member attempts topup -> 403 Forbidden
    member_topup = await client.post(
        "/api/v1/billing/topup",
        json={"amount": 500},
        headers=member_headers,
    )
    assert member_topup.status_code == 403
    err_msg = member_topup.json().get("error", {}).get("message") or member_topup.json().get(
        "detail", ""
    )
    assert "Admin privileges required" in err_msg

    # 4. Owner attempts topup -> 200 OK
    owner_topup = await client.post(
        "/api/v1/billing/topup",
        json={"amount": 500},
        headers=owner_headers,
    )
    assert owner_topup.status_code == 200
    assert owner_topup.json()["added"] == 500


@pytest.mark.asyncio
async def test_registration_role_assignment(client: httpx.AsyncClient):
    org_name = f"RoleOrg-{uuid.uuid4().hex[:6]}"

    # First user -> owner
    r1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"first-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "First User",
            "password": "Password123!",
            "org_name": org_name,
        },
    )
    assert r1.status_code == 201
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}
    me1 = await client.get("/api/v1/auth/me", headers=h1)
    assert me1.status_code == 200
    assert me1.json()["role"] == "owner"

    # Second user in same org -> member
    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"second-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Second User",
            "password": "Password123!",
            "org_name": org_name,
        },
    )
    assert r2.status_code == 201
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    me2 = await client.get("/api/v1/auth/me", headers=h2)
    assert me2.status_code == 200
    assert me2.json()["role"] == "member"

    # Anonymous user -> guest
    anon_resp = await client.post("/api/v1/auth/anonymous")
    assert anon_resp.status_code == 201
    anon_user = anon_resp.json()["user"]
    assert anon_user["role"] == "guest"


@pytest.mark.asyncio
async def test_token_encryption(client: httpx.AsyncClient, session_factory):
    # Register user
    email = f"tokens-{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Token Tester",
            "password": "Password123!",
            "org_name": f"TokensOrg-{uuid.uuid4().hex[:6]}",
        },
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # Update settings with tokens
    gh_raw = "ghp_testsecret12345"
    rnd_raw = "rnd_testsecret67890"
    vcl_raw = "vcl_testsecretabcdef"

    patch_resp = await client.patch(
        "/api/v1/auth/me/settings",
        json={
            "github_token": gh_raw,
            "render_api_key": rnd_raw,
            "vercel_token": vcl_raw,
        },
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["updated"] is True

    # Query DB directly to verify encryption at rest
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        settings = user.settings

        assert settings["github_token"].startswith("enc:")
        assert settings["github_token"] != gh_raw
        assert decrypt_secret(settings["github_token"]) == gh_raw

        assert settings["render_api_key"].startswith("enc:")
        assert settings["render_api_key"] != rnd_raw
        assert decrypt_secret(settings["render_api_key"]) == rnd_raw

        assert settings["vercel_token"].startswith("enc:")
        assert settings["vercel_token"] != vcl_raw
        assert decrypt_secret(settings["vercel_token"]) == vcl_raw


@pytest.mark.asyncio
async def test_regeneration_failure_refunds_credits(
    workspace_solution, session_factory, monkeypatch
):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    # 1. Create a base artifact (version 1) and set finite balance on org
    async with session_factory() as session:
        art = SolutionArtifact(
            solution_id=solution_id,
            artifact_type="hld",
            title="HLD Blueprint v1",
            content={"overview": "v1 content"},
            content_text="v1 original content text",
            version=1,
        )
        session.add(art)

        # Find org linked to solution
        from app.models.solution import Solution
        from app.models.workspace import Workspace

        sol_res = await session.execute(select(Solution).where(Solution.id == solution_id))
        sol = sol_res.scalar_one()
        ws_res = await session.execute(select(Workspace).where(Workspace.id == sol.workspace_id))
        ws = ws_res.scalar_one()
        org_res = await session.execute(select(Organization).where(Organization.id == ws.org_id))
        org = org_res.scalar_one()
        org.credits_remaining = 50
        await session.commit()

    # 2. Mock solutions_architect_node to fail
    async def mock_failing_node(state):
        raise RuntimeError("Simulated LLM connection timeout")

    monkeypatch.setattr(
        "app.api.artifacts.solutions_architect_node",
        mock_failing_node,
    )

    # 3. Call regenerate
    regen_resp = await client.post(
        "/api/v1/artifacts/regenerate",
        json={
            "solution_id": str(solution_id),
            "artifact_type": "hld",
            "user_feedback": "Add Kubernetes architecture",
        },
        headers=headers,
    )

    # 4. Must return 502 Bad Gateway
    assert regen_resp.status_code == 502
    err_msg = regen_resp.json().get("error", {}).get("message") or regen_resp.json().get(
        "detail", ""
    )
    assert "Regeneration agent failed" in err_msg

    # 5. Verify credits are refunded and no v2 artifact exists
    async with session_factory() as session:
        org_res = await session.execute(select(Organization).where(Organization.id == ws.org_id))
        org = org_res.scalar_one()
        # Initial 50, cost was deducted then refunded -> balance remains 50
        assert org.credits_remaining == 50

        # Artifacts count must still be 1 (only version 1)
        arts_res = await session.execute(
            select(SolutionArtifact).where(SolutionArtifact.solution_id == solution_id)
        )
        arts = arts_res.scalars().all()
        assert len(arts) == 1
        assert arts[0].version == 1


@pytest.mark.asyncio
async def test_business_analyst_history_preservation(monkeypatch):
    captured_messages = []

    class MockLLM:
        async def ainvoke(self, messages):
            nonlocal captured_messages
            captured_messages = messages
            mock_resp = AsyncMock()
            mock_resp.content = '{"requirements": ["auth", "payments"], "confidence_score": 0.85}'
            return mock_resp

    monkeypatch.setattr("app.agents.nodes.business_analyst.get_llm", lambda **kwargs: MockLLM())

    state = {
        "user_message": "Yes, we also need credit card support.",
        "conversation_history": [
            {"role": "user", "content": "I want to build a delivery app"},
            {"role": "assistant", "content": "What payment methods will you accept?"},
        ],
    }

    result = await business_analyst_node(state)
    assert result["confidence_score"] == 0.85

    # Check captured messages
    # Message 0: SystemMessage
    # Message 1: HumanMessage ("I want to build a delivery app")
    # Message 2: AIMessage ("What payment methods will you accept?")
    # Message 3: HumanMessage ("Yes, we also need credit card support.")
    assert len(captured_messages) == 4
    assert isinstance(captured_messages[1], HumanMessage)
    assert captured_messages[1].content == "I want to build a delivery app"
    assert isinstance(captured_messages[2], AIMessage)
    assert captured_messages[2].content == "What payment methods will you accept?"
    assert isinstance(captured_messages[3], HumanMessage)
    assert captured_messages[3].content == "Yes, we also need credit card support."
