"""Integration tests for chat (SSE), artifact regeneration/versioning,
exports, and the full workable-system lifecycle via the public API."""

import io
import json
import zipfile
from uuid import uuid4


def _parse_sse(text: str) -> list[dict]:
    events = []
    separator = "\r\n\r\n" if "\r\n\r\n" in text else "\n\n"
    for block in text.split(separator):
        event = None
        data = None
        for raw in block.splitlines():
            line = raw.strip()
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        if event:
            parsed = json.loads(data) if data else None
            events.append({"event": event, "data": parsed})
    return events


async def test_chat_send_runs_discovery_and_persists(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    sol_id = workspace_solution["solution_id"]

    resp = await client.post(
        "/api/v1/chat/send",
        json={
            "solution_id": sol_id,
            "message": "We run a B2B SaaS company selling CRM software and need a system "
            "with lead pipeline tracking",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert events[0]["event"] == "agent_start"
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["status"] == "complete"

    detail = await client.get(f"/api/v1/solutions/{sol_id}", headers=headers)
    assert detail.status_code == 200
    types = {a["artifact_type"] for a in detail.json()["artifacts"]}
    assert {"hld", "lld", "database_schema", "api_spec", "roadmap", "workable_schema"} <= types
    assert detail.json()["status"] == "complete"


async def test_chat_send_unknown_solution_404(workspace_solution):
    resp = await workspace_solution["client"].post(
        "/api/v1/chat/send",
        json={"solution_id": str(uuid4()), "message": "build a system"},
        headers=workspace_solution["headers"],
    )
    assert resp.status_code == 404


async def test_confirm_recommendations_generates(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    sol_id = workspace_solution["solution_id"]

    resp = await client.post(
        "/api/v1/chat/confirm-recommendations",
        json={"solution_id": sol_id, "accepted_modules": ["crm", "project_management"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["status"] == "complete"

    detail = await client.get(f"/api/v1/solutions/{sol_id}", headers=headers)
    assert any(a["artifact_type"] == "workable_schema" for a in detail.json()["artifacts"])


async def test_artifact_history_and_regeneration(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    sol_id = workspace_solution["solution_id"]

    await client.post(
        "/api/v1/chat/send",
        json={
            "solution_id": sol_id,
            "message": "We run a B2B SaaS company selling CRM software and need lead tracking",
        },
        headers=headers,
    )

    # History returns versions
    resp = await client.get(f"/api/v1/artifacts/{sol_id}/history/hld", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["artifact_type"] == "hld"

    # Regenerate the HLD → v2
    resp = await client.post(
        "/api/v1/artifacts/regenerate",
        json={"solution_id": sol_id, "artifact_type": "hld", "user_feedback": "Add SSO"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["artifact"]["version"] == 2
    assert resp.json()["status"] == "success"

    resp = await client.get(f"/api/v1/artifacts/{sol_id}/history/hld", headers=headers)
    assert len(resp.json()) == 2

    # Custom/unknown type uses the synthesized fallback branch
    resp = await client.post(
        "/api/v1/artifacts/regenerate",
        json={"solution_id": sol_id, "artifact_type": "security_policy", "user_feedback": "MFA"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["artifact"]["version"] == 1
    assert resp.json()["artifact"]["content"]["custom_spec"] == "MFA"

    # 404 flow
    resp = await client.post(
        "/api/v1/artifacts/regenerate",
        json={"solution_id": str(uuid4()), "artifact_type": "hld", "user_feedback": "x"},
        headers=headers,
    )
    assert resp.status_code == 404
    resp = await client.get(f"/api/v1/artifacts/{uuid4()}/history/hld", headers=headers)
    assert resp.status_code == 404


async def test_export_json_markdown_zip(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    sol_id = workspace_solution["solution_id"]

    resp = await client.post(
        "/api/v1/chat/send",
        json={
            "solution_id": sol_id,
            "message": "We run a B2B SaaS company selling CRM software and need lead tracking",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/export/{sol_id}/json", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == sol_id
    assert resp.headers["content-type"].startswith("application/json")

    resp = await client.get(f"/api/v1/export/{sol_id}/markdown", headers=headers)
    assert resp.status_code == 200
    assert resp.text.startswith("# Test Solution")

    resp = await client.get(f"/api/v1/export/{sol_id}/zip", headers=headers)
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert {"README.md", "Dockerfile", "docker-compose.yml", "init.sql"} <= names

    resp = await client.get(f"/api/v1/export/{uuid4()}/json", headers=headers)
    assert resp.status_code == 404


async def test_full_workable_lifecycle_via_api(workspace_solution):
    client = workspace_solution["client"]
    headers = workspace_solution["headers"]
    sol_id = workspace_solution["solution_id"]

    # Not provisioned yet → 404
    resp = await client.get(f"/api/v1/workable/{sol_id}/modules", headers=headers)
    assert resp.status_code == 404

    # Generate schema via chat so provisioning is possible
    resp = await client.post(
        "/api/v1/chat/send",
        json={
            "solution_id": sol_id,
            "message": "We run a B2B SaaS company selling CRM software and need lead tracking",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(f"/api/v1/workable/{sol_id}/provision", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "provisioned"
    assert payload["modules"]

    resp = await client.get(f"/api/v1/workable/{sol_id}/modules", headers=headers)
    assert resp.status_code == 200
    modules = {m["module"] for m in resp.json()["modules"]}
    assert "crm" in modules

    resp = await client.post(f"/api/v1/workable/{sol_id}/seed?rows=3", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["seeded"] >= 2

    resp = await client.get(f"/api/v1/workable/{sol_id}/crm", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["counts"]["leads"] >= 3

    # CRUD on the leads entity
    created = await client.post(
        f"/api/v1/workable/{sol_id}/crm/leads",
        json={"name": "Lead One"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    lead_id = created.json()["id"]

    listed = await client.get(f"/api/v1/workable/{sol_id}/crm/leads", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 4

    got = await client.get(f"/api/v1/workable/{sol_id}/crm/leads/{lead_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Lead One"

    patched = await client.patch(
        f"/api/v1/workable/{sol_id}/crm/leads/{lead_id}",
        json={"status": "closed"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "closed"

    deleted = await client.delete(f"/api/v1/workable/{sol_id}/crm/leads/{lead_id}", headers=headers)
    assert deleted.status_code == 204

    # Not-found branches
    resp = await client.get(f"/api/v1/workable/{sol_id}/nope", headers=headers)
    assert resp.status_code == 404
    resp = await client.get(f"/api/v1/workable/{sol_id}/crm/missing_table", headers=headers)
    assert resp.status_code == 404
    resp = await client.get(f"/api/v1/workable/{uuid4()}/modules", headers=headers)
    assert resp.status_code == 404
