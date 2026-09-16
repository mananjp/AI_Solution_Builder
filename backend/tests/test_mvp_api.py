"""Integration tests for the OpenCode MVP Builder API endpoints.

Uses the real dev DB + a mocked ``run_build`` so no sidecar is contacted.
The trigger endpoint runs the build in a background task; tests poll the
status endpoint until the job transitions out of 'building'.
"""

import asyncio
import io
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from app.services import mvp_builder as builder_mod

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_fake_run_build(write_files: list[str] | None = None):
    """Return a ``run_build`` stub that writes the requested files into the workspace."""

    async def fake(solution_id, ai_state, build_number, title=None, check_npm=True, **kwargs):
        ws = builder_mod.build_workspace_dir(solution_id, build_number)
        if write_files is None:
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "README.md").write_text(f"# {title or 'MVP'}\n", encoding="utf-8")
            (ws / "backend").mkdir(exist_ok=True)
            (ws / "backend" / "main.py").write_text("print('hello')\n", encoding="utf-8")
            return {
                "session_id": "sess-test",
                "local_dir": str(ws),
                "file_count": 2,
                "files": ["README.md", "backend/main.py"],
            }
        # Explicit file list mode (unused by current tests, kept for reuse)
        ws.mkdir(parents=True, exist_ok=True)
        for rel in write_files:
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(f"# {rel}\n", encoding="utf-8")
        return {
            "session_id": "sess-test",
            "local_dir": str(ws),
            "file_count": len(write_files),
            "files": write_files,
        }

    return fake


@pytest.fixture(autouse=True)
def _set_inline_worker(monkeypatch):
    monkeypatch.setattr("app.api.mvp.settings.WORKER_MODE", "inline")


async def _wait_for_finish(client, headers, build_id, retries=80):
    """Poll build status until it leaves 'building' or 'queued' (or timeout)."""
    for _ in range(retries):
        resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] not in ("building", "queued"):
            return body
        await asyncio.sleep(0.1)
    raise AssertionError("Build did not finish within polling window")


# ── Trigger ──────────────────────────────────────────────────────────────────


async def test_trigger_build_rejects_pending_solution(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]
    resp = await client.post(f"/api/v1/mvp/{solution_id}/build", json={}, headers=headers)
    assert resp.status_code == 409
    assert "must be generated" in resp.json()["error"]["message"]


async def test_trigger_build_and_complete_lifecycle(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    # Trigger with force (test solution status is 'discovery')
    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    build = resp.json()
    build_id = build["build_id"]
    assert build["status"] in ("queued", "building")
    assert build["file_count"] == 0

    # Wait for completion
    status = await _wait_for_finish(client, headers, build_id)
    assert status["status"] == "complete"
    assert status["file_count"] == 2
    assert status["error_message"] is None
    file_names = [f["path"] for f in status["files"]]
    assert "README.md" in file_names
    assert "backend/main.py" in file_names

    # List builds shows the completed one
    lst = await client.get(f"/api/v1/mvp/{solution_id}/builds", headers=headers)
    assert lst.status_code == 200
    ids = [b["build_id"] for b in lst.json()]
    assert build_id in ids

    # Download ZIP — assert 200 + valid zip (full content tested separately)
    dl = await client.get(f"/api/v1/mvp/builds/{build_id}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
        assert set(zf.namelist()) == {"README.md", "backend/main.py"}
        assert b"print('hello')" in zf.read("backend/main.py")


# ── Download ─────────────────────────────────────────────────────────────────


async def test_download_returns_valid_zip(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    await _wait_for_finish(client, headers, build_id)

    dl = await client.get(f"/api/v1/mvp/builds/{build_id}/download", headers=headers)
    assert dl.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
        assert "README.md" in zf.namelist()
        assert "backend/main.py" in zf.namelist()
        assert zf.read("README.md").startswith(b"# ")


async def test_download_not_complete_returns_409(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    # Fake that sleeps forever so the build stays in 'building' state
    async def _never_finish(solution_id, ai_state, build_number, title=None):
        await asyncio.sleep(3600)  # pragma: no cover
        return {"session_id": "s", "local_dir": "/tmp/x", "file_count": 0, "files": []}

    monkeypatch.setattr("app.api.mvp.builder.run_build", _never_finish)

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]

    # Immediately try to download — should be 409 (still 'building')
    dl = await client.get(f"/api/v1/mvp/builds/{build_id}/download", headers=headers)
    assert dl.status_code == 409


# ── Configure ────────────────────────────────────────────────────────────────


async def test_configure_applies_overlay(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    status = await _wait_for_finish(client, headers, build_id)

    cfg = await client.post(
        f"/api/v1/mvp/builds/{build_id}/configure",
        json={"app_name": "My Product", "env": {"JWT_SECRET": "abc123", "PORT": "8080"}},
        headers=headers,
    )
    assert cfg.status_code == 200, cfg.text
    assert cfg.json()["applied"]["app_name"] == "My Product"
    assert cfg.json()["applied"]["JWT_SECRET"] == "abc123"

    # Response exposes a project-relative workspace slug, never the server path.
    from app.core.config import settings

    ws = Path(settings.MVP_BUILD_DIR) / status["workspace_path"]
    assert (ws / ".env.local").exists()
    env_content = (ws / ".env.local").read_text(encoding="utf-8")
    assert "JWT_SECRET=abc123" in env_content
    assert "PORT=8080" in env_content
    assert (ws / "README.md").read_text(encoding="utf-8").startswith("# My Product")


async def test_configure_rejects_building_status(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    # Fake that sleeps forever so the build stays in 'building' state
    async def _never_finish(
        solution_id, ai_state, build_number, title=None, check_npm=True, **kwargs
    ):
        await asyncio.sleep(3600)  # pragma: no cover
        return {"session_id": "s", "local_dir": "/tmp/x", "file_count": 0, "files": []}

    monkeypatch.setattr("app.api.mvp.builder.run_build", _never_finish)

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]

    cfg = await client.post(
        f"/api/v1/mvp/builds/{build_id}/configure",
        json={"app_name": "Bad"},
        headers=headers,
    )
    assert cfg.status_code == 409


# ── Destroy ──────────────────────────────────────────────────────────────────


async def test_destroy_removes_workspace(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    status = await _wait_for_finish(client, headers, build_id)
    from app.core.config import settings

    ws = Path(settings.MVP_BUILD_DIR) / status["workspace_path"]
    assert ws.exists()

    del_resp = await client.delete(f"/api/v1/mvp/builds/{build_id}", headers=headers)
    assert del_resp.status_code == 204
    assert not ws.exists()


# ── Cross-user isolation ─────────────────────────────────────────────────────


async def test_build_status_404_for_other_user(workspace_solution, monkeypatch):
    """A second user must not be able to read another user's build."""
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    await _wait_for_finish(client, headers, build_id)

    # A second, genuinely distinct user must not see the build.
    other_email = f"intruder-{uuid4().hex[:8]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": other_email,
            "full_name": "Intruder",
            "password": "Testpass123!",
            "org_name": "Intruder-Org",
        },
    )
    assert reg.status_code == 201, reg.text
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=other_headers)
    assert resp.status_code == 404


# ── Templates ────────────────────────────────────────────────────────────────


async def test_list_templates_endpoint(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    resp = await client.get("/api/v1/mvp/templates", headers=headers)
    assert resp.status_code == 200, resp.text
    slugs = {t["slug"] for t in resp.json()}
    assert {"todo", "calculator", "portfolio"} <= slugs


async def test_build_uses_template_seed(workspace_solution, monkeypatch):
    """A template build seeds ai_state with the preset if the solution has none."""
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    captured = {}

    async def fake_run(solution_id, ai_state, build_number, title=None, check_npm=True, **kwargs):
        captured["ai_state"] = ai_state
        captured["module"] = (ai_state.get("confirmed_modules") or ["none"])[0]
        captured["title"] = title
        ws = builder_mod.build_workspace_dir(solution_id, build_number)
        (ws / "README.md").write_text("# ok\n", encoding="utf-8")
        return {
            "session_id": "sess-tpl",
            "local_dir": str(ws),
            "file_count": 1,
            "files": ["README.md"],
        }

    monkeypatch.setattr("app.api.mvp.builder.run_build", fake_run)
    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build",
        json={"force": True, "template": "todo", "app_name": "QuickTodos"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    build_id = resp.json()["build_id"]
    body = await _wait_for_finish(client, headers, build_id)
    assert body["status"] == "complete"
    assert captured["module"] == "task_management"
    assert captured["title"] == "QuickTodos"


# ── Deploy ───────────────────────────────────────────────────────────────────


async def test_deploy_requires_github_token(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())
    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    await _wait_for_finish(client, headers, build_id)

    resp = await client.post(
        f"/api/v1/mvp/builds/{build_id}/deploy",
        json={"repo_name": "my-app"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "GitHub token" in resp.json()["error"]["message"]


async def test_deploy_pushes_workspace_to_github(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    # Save a GitHub token on the profile.
    resp = await client.patch(
        "/api/v1/auth/me/settings", json={"github_token": "ghp_demotoken123"}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    build = await _wait_for_finish(client, headers, build_id)
    assert build["status"] == "complete"

    fake_result = {
        "url": "https://github.com/testowner/demo-app",
        "clone_url": "https://github.com/testowner/demo-app.git",
        "owner": "testowner",
        "branch": "main",
    }

    async def fake_deploy(**kwargs):
        assert kwargs["gh_token"] == "ghp_demotoken123"
        assert kwargs["repo_name"] == "demo-app"
        return {**fake_result, "file_count": 2}

    monkeypatch.setattr("app.api.mvp._deploy_workspace_to_github", fake_deploy)
    resp = await client.post(
        f"/api/v1/mvp/builds/{build_id}/deploy",
        json={"repo_name": "demo-app"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_url"] == "https://github.com/testowner/demo-app"

    # repo_url now available on status, redeploy blocked without force.
    resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=headers)
    assert resp.json()["repo_url"] == "https://github.com/testowner/demo-app"
    resp = await client.post(
        f"/api/v1/mvp/builds/{build_id}/deploy",
        json={"repo_name": "demo-app"},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_deploy_with_render_token_triggers_auto_deploy(workspace_solution, monkeypatch):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    # Save both GitHub token and Render API key on the profile.
    resp = await client.patch(
        "/api/v1/auth/me/settings",
        json={"github_token": "ghp_demotoken123", "render_api_key": "rnd_livekey456"},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    build = await _wait_for_finish(client, headers, build_id)
    assert build["status"] == "complete"

    async def fake_deploy(**kwargs):
        return {
            "url": "https://github.com/testowner/render-app",
            "clone_url": "https://github.com/testowner/render-app.git",
            "owner": "testowner",
            "branch": "main",
            "file_count": 5,
        }

    monkeypatch.setattr("app.api.mvp._deploy_workspace_to_github", fake_deploy)

    async def fake_render_deploy(self, repo_url, repo_name, branch="main", **kwargs):
        return {
            "service_id": "srv-test-999",
            "service_url": "https://render-app-web.onrender.com",
            "dashboard_url": "https://dashboard.render.com/web/srv-test-999",
            "deploy_url": f"https://render.com/deploy?repo={repo_url}",
            "status": "deployed",
            "message": "Service successfully provisioned on Render.",
        }

    async def fake_destroy_service(self, service_id):
        assert service_id == "srv-test-999"
        return True

    monkeypatch.setattr("app.api.mvp.RenderDeployer.deploy_repo", fake_render_deploy)
    monkeypatch.setattr("app.api.mvp.RenderDeployer.destroy_service", fake_destroy_service)

    resp = await client.post(
        f"/api/v1/mvp/builds/{build_id}/deploy",
        json={"repo_name": "render-app"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo_url"] == "https://github.com/testowner/render-app"
    assert data["render_service_url"] == "https://render-app-web.onrender.com"
    assert data["render_dashboard_url"] == "https://dashboard.render.com/web/srv-test-999"
    assert "https://render.com/deploy?repo=" in data["render_deploy_url"]

    # Check status endpoint reflects Render URLs
    resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=headers)
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["render_service_url"] == "https://render-app-web.onrender.com"

    # Test preview destroy endpoint
    resp = await client.post(f"/api/v1/mvp/builds/{build_id}/preview/destroy", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["destroyed"] is True

    # Status endpoint should now have cleared the service URL
    resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=headers)
    assert resp.json()["render_service_url"] is None


# ── Cloudinary storage redirect ─────────────────────────────────────────────


async def test_download_redirects_when_storage_key_set(workspace_solution, monkeypatch):
    """When a build has a storage_key, download returns 307 to Cloudinary URL."""
    from unittest.mock import AsyncMock, patch

    from app.services.storage import CloudinaryStorage

    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    solution_id = workspace_solution["solution_id"]

    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        f"/api/v1/mvp/{solution_id}/build", json={"force": True}, headers=headers
    )
    build_id = resp.json()["build_id"]
    await _wait_for_finish(client, headers, build_id)

    # Patch the build's storage_key directly in the DB
    from app.core.database import async_session_factory
    from app.models.mvp_build import MVPBuild

    async with async_session_factory() as db:
        build = await db.get(MVPBuild, build_id)
        assert build is not None
        build.storage_key = "builds/test/build_1.zip"
        await db.commit()

    # Mock get_storage to return a mock CloudinaryStorage with a secure URL
    download_url = "https://res.cloudinary.com/test-cloud/raw/upload/builds/test/build_1.zip"
    mock_storage = AsyncMock(spec=CloudinaryStorage)
    mock_storage.get_download_url = AsyncMock(return_value=download_url)

    with patch("app.api.mvp.get_storage", return_value=mock_storage):
        # Use a separate client that does NOT follow redirects to inspect the 307
        import httpx
        from httpx import ASGITransport

        from main import app

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=False
        ) as no_follow_client:
            dl = await no_follow_client.get(
                f"/api/v1/mvp/builds/{build_id}/download", headers=headers
            )

    assert dl.status_code == 307, f"Expected 307, got {dl.status_code}: {dl.text}"
    assert dl.headers["location"] == download_url
