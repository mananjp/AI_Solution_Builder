"""
Tests for Render automated deployer (app.services.render_deployer).
"""

import pytest

from app.services.render_deployer import (
    RenderDeployer,
    RenderDeployError,
    clean_service_name,
    get_1click_deploy_url,
)


def test_clean_service_name():
    assert clean_service_name("My_Awesome_App") == "my-awesome-app"
    assert clean_service_name("---Hello---World---") == "hello-world"
    assert clean_service_name("Special#@!Chars123") == "special-chars123"
    assert clean_service_name("") == "app"
    # Verify length constraint
    long_name = "a" * 50
    assert len(clean_service_name(long_name)) <= 30


def test_get_1click_deploy_url():
    url = get_1click_deploy_url("https://github.com/user/demo-repo")
    assert url == "https://render.com/deploy?repo=https://github.com/user/demo-repo"
    assert get_1click_deploy_url("") == "https://render.com/deploy"


@pytest.mark.asyncio
async def test_render_deployer_requires_key():
    with pytest.raises(RenderDeployError, match="Render API key is required"):
        RenderDeployer("")


class _FakeRenderResponse:
    def __init__(self, status_code: int, json_data: dict | list | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or str(json_data or "")

    def json(self):
        return self._json


@pytest.mark.asyncio
async def test_get_owner_id_success(monkeypatch):
    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _FakeRenderResponse(
                200,
                [
                    {
                        "owner": {
                            "id": "usr-test-owner-123",
                            "name": "Test User",
                            "email": "test@example.com",
                        }
                    }
                ],
            )

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_validtoken123")
    owner_id = await deployer.get_owner_id()
    assert owner_id == "usr-test-owner-123"


@pytest.mark.asyncio
async def test_get_owner_id_unauthorized(monkeypatch):
    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _FakeRenderResponse(401, text="Unauthorized: Invalid API key")

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_invalid")
    with pytest.raises(RenderDeployError, match="Failed to retrieve Render workspaces"):
        await deployer.get_owner_id()


@pytest.mark.asyncio
async def test_deploy_repo_success(monkeypatch):
    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _FakeRenderResponse(
                200,
                [{"owner": {"id": "usr-123"}}],
            )

        async def post(self, url, json, **kwargs):
            return _FakeRenderResponse(
                201,
                {
                    "service": {
                        "id": "srv-prod-456",
                        "name": json["name"],
                        "dashboardUrl": "https://dashboard.render.com/web/srv-prod-456",
                        "serviceDetails": {
                            "url": "https://demo-app-web.onrender.com",
                        },
                    },
                    "deployId": "dep-789",
                },
            )

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_secret_token")
    res = await deployer.deploy_repo(
        repo_url="https://github.com/user/demo-app",
        repo_name="demo-app",
    )

    assert res["status"] in ("deployed", "deploying")
    assert res["service_id"] == "srv-prod-456"
    assert res["service_url"] == "https://demo-app-web.onrender.com"
    assert res["frontend_url"] == "https://demo-app-web.onrender.com"
    assert res["dashboard_url"] == "https://dashboard.render.com/web/srv-prod-456"
    assert res["deploy_url"] == "https://render.com/deploy?repo=https://github.com/user/demo-app"


@pytest.mark.asyncio
async def test_deploy_repo_existing_service(monkeypatch):
    deploys_triggered = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None, **kwargs):
            if "owners" in url:
                return _FakeRenderResponse(200, [{"owner": {"id": "usr-123"}}])
            if "services" in url:
                name = (params or {}).get("name", "")
                return _FakeRenderResponse(
                    200,
                    [
                        {
                            "service": {
                                "id": f"srv-{name}",
                                "name": name,
                                "dashboardUrl": f"https://dashboard.render.com/web/srv-{name}",
                                "serviceDetails": {
                                    "url": f"https://{name}.onrender.com",
                                },
                            }
                        }
                    ],
                )
            return _FakeRenderResponse(404)

        async def post(self, url, json=None, **kwargs):
            if "deploys" in url:
                deploys_triggered.append(url)
                return _FakeRenderResponse(201, {"id": "dep-new-123"})
            return _FakeRenderResponse(500)

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_secret_token")
    res = await deployer.deploy_repo(
        repo_url="https://github.com/user/existing-app",
        repo_name="existing-app",
    )

    assert res["status"] in ("deployed", "deploying")
    assert res["frontend_url"] == "https://existing-app.onrender.com"
    assert res["service_url"] == "https://existing-app.onrender.com"
    assert len(deploys_triggered) >= 1


@pytest.mark.asyncio
async def test_deploy_repo_fallback_on_api_error(monkeypatch):
    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _FakeRenderResponse(200, [{"owner": {"id": "usr-123"}}])

        async def post(self, url, json, **kwargs):
            return _FakeRenderResponse(400, text="GitHub repository requires organization grant")

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_secret_token")
    res = await deployer.deploy_repo(
        repo_url="https://github.com/user/private-app",
        repo_name="private-app",
    )

    assert res["status"] == "pending_connection"
    assert res["service_url"] is None
    assert "render.com/deploy?repo=" in res["deploy_url"]


@pytest.mark.asyncio
async def test_destroy_service(monkeypatch):
    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def delete(self, url, **kwargs):
            return _FakeRenderResponse(204)

    monkeypatch.setattr(
        "app.services.render_deployer.httpx.AsyncClient", lambda *a, **k: _FakeClient()
    )

    deployer = RenderDeployer("rnd_secret_token")
    success = await deployer.destroy_service("srv-prod-456")
    assert success is True


def test_sanitize_render_yaml_converts_legacy_pgsql():
    from app.services.deployer import _sanitize_render_yaml

    legacy = """services:
  - name: my-cool-app-db
    type: pgsql
    plan: starter
    database: my-cool-app

  - name: my-cool-app-backend
    type: web
    runtime: docker
    plan: starter
    dockerfilePath: ./backend/Dockerfile

  - name: my-cool-app-frontend
    type: web
    runtime: docker
    plan: starter
    dockerfilePath: ./frontend/Dockerfile
    buildCommand: npm install && npm run build
    startCommand: npm run start
"""
    sanitized = _sanitize_render_yaml(legacy)
    assert "databases:" in sanitized
    assert "- name: my-cool-app-db" in sanitized
    assert "databaseName: my_cool_app" in sanitized
    assert "plan: free" in sanitized
    assert "dockerContext: ./backend" in sanitized
    assert "dockerContext: ./frontend" in sanitized
    assert "type: pgsql" not in sanitized
    assert "buildCommand:" not in sanitized
    assert "startCommand:" not in sanitized
