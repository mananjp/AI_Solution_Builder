"""Integration tests for the one-click quick-build endpoint (premade apps).

Uses the real dev DB + mocked ``run_build`` so no sidecar is contacted.
The auto-created solution must be born ``status="complete"`` so the 409 guard
never fires for the premade path.
"""

import asyncio

import pytest

from app.services import mvp_builder as builder_mod


def _make_fake_run_build():
    """Return a ``run_build`` stub that writes a README into the workspace."""

    async def fake(solution_id, ai_state, build_number, title=None, check_npm=True, **kwargs):
        ws = builder_mod.build_workspace_dir(solution_id, build_number)
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "README.md").write_text(f"# {title or 'MVP'}\n", encoding="utf-8")
        return {
            "session_id": "sess-quick",
            "local_dir": str(ws),
            "file_count": 1,
            "files": ["README.md"],
        }

    return fake


@pytest.fixture(autouse=True)
def _set_inline_worker(monkeypatch):
    monkeypatch.setattr("app.api.mvp.settings.WORKER_MODE", "inline")


async def _wait_for_finish(client, headers, build_id, retries=80):
    for _ in range(retries):
        resp = await client.get(f"/api/v1/mvp/builds/{build_id}/status", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] not in ("building", "queued"):
            return body
        await asyncio.sleep(0.05)
    raise AssertionError("Build did not finish within polling window")


async def test_quick_build_unknown_template_404(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers"]
    resp = await client.post("/api/v1/mvp/quick-build", json={"template": "nope"}, headers=headers)
    assert resp.status_code == 404


async def test_quick_build_creates_solution_and_completes(auth_client, monkeypatch):
    client = auth_client["client"]
    headers = auth_client["headers"]
    monkeypatch.setattr("app.api.mvp.builder.run_build", _make_fake_run_build())

    resp = await client.post(
        "/api/v1/mvp/quick-build",
        json={"template": "todo", "app_name": "MyTodo"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("queued", "building")
    build_id = body["build_id"]

    status = await _wait_for_finish(client, headers, build_id)
    assert status["status"] == "complete"
    assert status["file_count"] == 1

    # Auto-created solution is born 'complete' and carries the app name.
    sol_resp = await client.get(f"/api/v1/solutions/{body['solution_id']}", headers=headers)
    assert sol_resp.status_code == 200
    sol = sol_resp.json()
    assert sol["status"] == "complete"
    assert sol["title"] == "MyTodo"


async def test_quick_build_seeds_template_ai_state(auth_client, monkeypatch):
    """The build receives the template's seeded ai_state (template already
    'complete', so the payload passes even without force)."""
    client = auth_client["client"]
    headers = auth_client["headers"]

    captured = {}

    async def fake_run(solution_id, ai_state, build_number, title=None, check_npm=True, **kwargs):
        captured["ai_state"] = ai_state
        captured["module"] = (ai_state.get("confirmed_modules") or ["none"])[0]
        ws = builder_mod.build_workspace_dir(solution_id, build_number)
        (ws / "README.md").write_text("# ok\n", encoding="utf-8")
        return {
            "session_id": "sess-seed",
            "local_dir": str(ws),
            "file_count": 1,
            "files": ["README.md"],
        }

    monkeypatch.setattr("app.api.mvp.builder.run_build", fake_run)
    resp = await client.post(
        "/api/v1/mvp/quick-build",
        json={"template": "todo"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    await _wait_for_finish(client, headers, resp.json()["build_id"])
    assert captured["module"] == "task_management"
