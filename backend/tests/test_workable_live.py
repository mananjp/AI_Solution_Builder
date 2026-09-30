"""
Workable System end-to-end smoke test (requires a running test database).

Covers:
  register → workspace → solution → mock pipeline → provision → seed → module index → CRUD
"""

import uuid

import pytest_asyncio
from sqlalchemy import text as sa_text
from sqlalchemy.future import select

from app.agents.graph import discovery_graph
from app.models.solution import Solution

TEST_USER = {
    "email": f"test-workable-{uuid.uuid4().hex[:8]}@example.com",
    "full_name": "Workable Tester",
    "password": "Testpass123!",
    "org_name": "WorkableTestOrg",
}


@pytest_asyncio.fixture()
async def client_and_db(client, session_factory, db_engine):
    """Reuse the shared client and session-scoped engine instead of a second pool.

    A second engine meant a second set of asyncpg connections with its own teardown
    ordering, which is what surfaced ``RuntimeError: Event loop is closed``.
    """
    return client, session_factory, db_engine


async def test_workable_end_to_end(client_and_db):
    client, session_factory, engine = client_and_db

    # 1. Register → get JWT
    resp = await client.post("/api/v1/auth/register", json=TEST_USER)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create workspace
    resp = await client.post("/api/v1/workspaces", json={"name": "Workable WS"}, headers=headers)
    assert resp.status_code == 201, resp.text
    workspace_id = resp.json()["id"]

    # 3. Create solution
    resp = await client.post(
        "/api/v1/solutions",
        json={"workspace_id": workspace_id, "title": "Workable Solution"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    solution_id = resp.json()["id"]

    # 4. Run mock discovery pipeline + persist (mirrors chat.py logic)
    initial_state = {
        "user_message": "Build me a CRM and project tracker",
        "conversation_history": [],
        "agent_messages": [],
    }
    final_state = await discovery_graph.ainvoke(initial_state)
    end_status = "complete" if final_state.get("generated_schema") else "error"

    async with session_factory() as db:
        sol = (await db.execute(select(Solution).where(Solution.id == solution_id))).scalar_one()
        sol.ai_state = {
            k: v for k, v in final_state.items() if k != "agent_messages" and not callable(v)
        }
        sol.status = end_status
        await db.commit()

    assert end_status == "complete", f"Pipeline ended with status: {end_status}"
    assert final_state.get("workable_modules"), "No workable_modules produced"
    assert final_state["generated_schema"]["content"].get("ddl"), "No DDL in generated schema"

    # 5. Provision tenant schema
    resp = await client.post(
        f"/api/v1/workable/{solution_id}/provision",
        json={"force": False},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    prov = resp.json()
    schema_name = prov["schema_name"]
    assert prov["status"] == "provisioned", prov
    module_names = [m["module"] for m in prov["modules"]]
    assert len(module_names) >= 2, f"Expected >=2 modules, got {module_names}"

    # 6. Seed synthetic rows
    resp = await client.post(f"/api/v1/workable/{solution_id}/seed?rows=3", headers=headers)
    assert resp.status_code == 200, resp.text
    seed_info = resp.json()
    assert seed_info["seeded"] >= 3, seed_info

    # 7. Module index → pick a populated entity (prefer one with a `name` column)
    first_module = module_names[0]
    resp = await client.get(f"/api/v1/workable/{solution_id}/{first_module}", headers=headers)
    assert resp.status_code == 200, resp.text
    mod = resp.json()

    async def _columns(entity: str) -> set[str]:
        async with engine.connect() as conn:
            result = await conn.execute(
                sa_text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = :s AND table_name = :e"
                ),
                {"s": schema_name, "e": entity},
            )
            return {r["column_name"] for r in result.mappings()}

    populated = [e for e, c in mod["counts"].items() if c > 0]
    assert populated, f"No populated entities in module '{first_module}': {mod['counts']}"
    nvalid = [e for e in populated if "name" in (await _columns(e))]
    entity = (nvalid or populated)[0]
    cols = await _columns(entity)

    # 8. List rows (page 1)
    resp = await client.get(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    list_resp = resp.json()
    assert list_resp["total"] >= 1, list_resp

    # 9. Create a new row (payload built from live column metadata)
    create_payload = {"name": "Manual Test Record"} if "name" in cols else {}
    if "status" in cols:
        create_payload["status"] = "new"
    if "company" in cols:
        create_payload["company"] = "Acme Corp"
    assert create_payload, f"No writeable columns available on '{entity}'"
    resp = await client.post(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}",
        json=create_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    new_row = resp.json()
    new_id = new_row["id"]
    assert new_row.get("name") == "Manual Test Record"

    # 10. Get the new row
    resp = await client.get(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}/{new_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("name", new_id) == new_row.get("name", new_id)

    # 11. Patch the new row (updates the name column, keeping others intact)
    patch_value = "Updated Test Record" if "name" in cols else None
    patch_payload = {"name": patch_value} if patch_value else {"company": "Updated Corp"}
    resp = await client.patch(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}/{new_id}",
        json=patch_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("name") in ("Updated Test Record", None)

    # 12. Delete the new row
    resp = await client.delete(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}/{new_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    # 13. Confirm deletion → 404
    resp = await client.get(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}/{new_id}",
        headers=headers,
    )
    assert resp.status_code == 404

    # 14. Verify original seeded rows still intact
    resp = await client.get(
        f"/api/v1/workable/{solution_id}/{first_module}/{entity}",
        headers=headers,
    )
    assert resp.json()["total"] >= 1

    # Cleanup tenant schema
    async with engine.begin() as conn:
        await conn.execute(sa_text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
