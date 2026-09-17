"""Integration tests for Enhanced Auth: Social Providers, Anonymous Guest, and OAuth."""

import httpx
import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_get_providers_empty(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "AUTH_GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AUTH_GOOGLE_CLIENT_SECRET", "")

    resp = await client.get("/api/v1/auth/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"] == []
    assert data["allow_anonymous"] is True


@pytest.mark.asyncio
async def test_get_providers_with_credentials(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_ID", "gh-client-123")
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_SECRET", "gh-secret-456")
    monkeypatch.setattr(settings, "AUTH_GOOGLE_CLIENT_ID", "")  # half-configured, shouldn't appear
    monkeypatch.setattr(settings, "AUTH_GOOGLE_CLIENT_SECRET", "google-secret-only")

    resp = await client.get("/api/v1/auth/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "github" in data["providers"]
    assert "google" not in data["providers"]  # Verified: half-configured omitted!


@pytest.mark.asyncio
async def test_anonymous_login_flow(client: httpx.AsyncClient):
    resp = await client.post("/api/v1/auth/anonymous")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["is_anonymous"] is True
    assert data["credits_remaining"] is None
    user = data["user"]
    assert user["is_anonymous"] is True
    assert user["auth_provider"] == "anonymous"
    assert "guest_" in user["email"]

    # Verify access to /me with the guest token
    guest_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_resp = await client.get("/api/v1/auth/me", headers=guest_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["is_anonymous"] is True


@pytest.mark.asyncio
async def test_upgrade_anonymous_account(client: httpx.AsyncClient):
    # 1. Start as guest
    anon_resp = await client.post("/api/v1/auth/anonymous")
    assert anon_resp.status_code == 201
    token = anon_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upgrade to permanent account
    from uuid import uuid4

    unique_email = f"permanent_{uuid4().hex[:8]}@company.com"
    upgrade_payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
        "full_name": "Senior Architect",
        "org_name": "Permanent Architecture Corp",
    }
    upgrade_resp = await client.post(
        "/api/v1/auth/upgrade-anonymous",
        json=upgrade_payload,
        headers=headers,
    )
    assert upgrade_resp.status_code == 200, upgrade_resp.text
    upgraded = upgrade_resp.json()
    assert upgraded["email"] == unique_email
    assert upgraded["full_name"] == "Senior Architect"
    assert upgraded["is_anonymous"] is False
    assert upgraded["auth_provider"] == "local"

    # 3. Verify user can now log in with standard email/password credentials
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "StrongPassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_oauth_authorize_url(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_ID", "gh-client-xyz")
    monkeypatch.setattr(settings, "AUTH_GITHUB_CLIENT_SECRET", "gh-secret-xyz")

    resp = await client.get("/api/v1/auth/oauth/github/authorize")
    assert resp.status_code == 200
    url = resp.json()["authorization_url"]
    assert "https://github.com/login/oauth/authorize" in url
    assert "client_id=gh-client-xyz" in url
