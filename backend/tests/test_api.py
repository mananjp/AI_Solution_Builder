"""Integration tests for the public API surface (system, auth, workspaces,
solutions, billing, admin, upload)."""

import uuid

from sqlalchemy import select

from app.core.security import (
    DEV_DEMO_EMAIL,
    DEV_DEMO_PASSWORD,
    create_access_token,
    ensure_dev_demo_user,
    hash_password,
)
from app.models.user import User


async def test_health_ready_metrics_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "docs" in resp.json()

    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp = await client.get("/ready")
    assert resp.status_code in (200, 503)
    assert "checks" in resp.json()

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


async def test_dev_demo_account_seed_and_login(session_factory, client):
    async with session_factory() as db:
        await ensure_dev_demo_user(db)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": DEV_DEMO_EMAIL, "password": DEV_DEMO_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


async def test_register_login_me_flows(client):
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Auth User",
            "password": "Supersecret1!",
            "org_name": "Auth Org",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Duplicate email → 409
    dup = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Auth User",
            "password": "Supersecret1!",
            "org_name": "Auth Org",
        },
    )
    assert dup.status_code == 409, dup.text
    assert dup.json()["error"]["code"] == "CONFLICT"

    # Login ok
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Supersecret1!"}
    )
    assert resp.status_code == 200, resp.text

    # Login wrong password → 401 envelope
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    # Me
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == email

    # Missing token → 401 envelope
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401, resp.text


async def test_registration_validation_error_envelope(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "full_name": "", "password": "x", "org_name": ""},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_workspace_crud(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.post("/api/v1/workspaces", json={"name": "WS 1"}, headers=headers)
    assert resp.status_code == 201, resp.text
    ws = resp.json()
    ws_id = ws["id"]

    # List
    resp = await client.get("/api/v1/workspaces", headers=headers)
    assert resp.status_code == 200
    assert any(w["id"] == ws_id for w in resp.json())

    # Get + 404
    resp = await client.get(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "WS 1"
    resp = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404

    # Patch
    resp = await client.patch(
        f"/api/v1/workspaces/{ws_id}", json={"name": "WS 1 renamed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "WS 1 renamed"

    # Delete → get 404
    resp = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert resp.status_code == 404


async def test_solution_flow(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    ws_id = workspace_solution["workspace_id"]
    sol_id = workspace_solution["solution_id"]

    # Create with bad workspace → 404
    resp = await client.post(
        "/api/v1/solutions",
        json={"workspace_id": str(uuid.uuid4()), "title": "Bad"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text

    # List
    resp = await client.get(f"/api/v1/solutions/workspace/{ws_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Get
    resp = await client.get(f"/api/v1/solutions/{sol_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["artifacts"] == []

    # Get unknown → 404
    resp = await client.get(f"/api/v1/solutions/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404

    # Delete
    resp = await client.delete(f"/api/v1/solutions/{sol_id}", headers=headers)
    assert resp.status_code == 204


async def test_billing_plans_usage_transactions_topup(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = await client.get("/api/v1/billing/usage", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["current_balance"] >= 0

    resp = await client.get("/api/v1/billing/transactions", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "demo-tx-1"

    resp = await client.post("/api/v1/billing/topup", json={"amount": 500}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["added"] == 500

    resp = await client.post("/api/v1/billing/topup", json={"amount": 0}, headers=headers)
    assert resp.status_code == 400


async def test_admin_endpoints(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 200
    assert "total_users" in resp.json()

    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 200
    assert any(u["email"] == auth_client["email"] for u in resp.json())

    resp = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert resp.status_code == 200


async def test_admin_forbidden_for_member(auth_client, session_factory):
    client = auth_client["client"]
    org_id = None
    async with session_factory() as db:
        me = (await db.execute(select(User).where(User.email == auth_client["email"]))).scalar_one()
        org_id = me.org_id
        member = User(
            email=f"member-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Member",
            hashed_password=hash_password("Testpass123!"),
            role="member",
            org_id=org_id,
        )
        db.add(member)
        await db.commit()
        member_id = member.id

    member_headers = {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(member_id)})}"
    }
    resp = await client.get("/api/v1/admin/stats", headers=member_headers)
    assert resp.status_code == 403
    assert "ELEVATED" in resp.text.upper()


async def test_upload_document(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.post(
        "/api/v1/upload/document",
        files={"file": ("notes.txt", b"hello world\nsecond line", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "hello world" in resp.json()["extracted_text"]

    resp = await client.post(
        "/api/v1/upload/document",
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BAD_REQUEST"

    resp = await client.post(
        "/api/v1/upload/document",
        files={"file": ("big.txt", b"x" * (11 * 1024 * 1024), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 413


async def test_upload_url_endpoint_parses(auth_client, monkeypatch):
    import app.api.upload as upload_module

    async def fake_parse_url(url):
        return f"Fetched content from {url}"

    monkeypatch.setattr(upload_module, "parse_url", fake_parse_url)
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.post(
        "/api/v1/upload/url",
        json={"url": "https://example.com/page"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"] == "https://example.com/page"
    assert "Fetched content" in body["extracted_text"]
    assert body["character_count"] == len(body["extracted_text"])


async def test_upload_url_unreachable_returns_422(auth_client, monkeypatch):
    import app.api.upload as upload_module

    async def bad_parse_url(url):
        raise ValueError(f"Failed to fetch {url}: boom")

    monkeypatch.setattr(upload_module, "parse_url", bad_parse_url)
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.post(
        "/api/v1/upload/url",
        json={"url": "https://unreachable.example"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert "Failed to fetch" in resp.json()["error"]["message"]
