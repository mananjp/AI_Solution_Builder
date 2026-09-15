"""Edge-case tests for the workable engine, schema provisioner, synthetic
seed generator, and the pluggable LLM provider layer."""

import json
from datetime import date

import pytest
import pytest_asyncio
from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text as sa_text

from app.core.llm import (
    MockChatModel,
    _build_mock_content,
    _mock_process_intelligence,
    get_llm,
    has_llm_credentials,
)
from app.models.solution import Solution
from app.services.synthetic import seed_synthetic_rows
from app.workable.engine import (
    create_row,
    delete_row,
    get_row,
    list_rows,
    resolve_table,
    update_row,
)
from app.workable.schema_provisioner import (
    _assign_entities_to_modules,
    _extract_schema_artifacts,
    _sanitize_schema_name,
    provision_workable_schema,
)

_KITCHEN_DDL = """
CREATE TABLE {schema_name}.kitchen_sink (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    price NUMERIC(10,2),
    is_active BOOLEAN NOT NULL,
    due_date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    extra_json JSONB
);
CREATE TABLE {schema_name}.child (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID NOT NULL REFERENCES {schema_name}.kitchen_sink(id),
    label VARCHAR(50)
);
"""


@pytest_asyncio.fixture()
async def extras_schemas(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS extras"))
        await conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS extras_seed"))
        for schema in ("extras", "extras_seed"):
            for stmt in [
                f"DROP TABLE IF EXISTS {schema}.child",
                f"DROP TABLE IF EXISTS {schema}.kitchen_sink",
                f"DROP TABLE IF EXISTS {schema}.composite",
                f"DROP TABLE IF EXISTS {schema}.nopk",
                f"DROP TABLE IF EXISTS {schema}.intpk",
            ]:
                await conn.execute(sa_text(stmt))
            for statement in [
                s for s in _KITCHEN_DDL.format(schema_name=schema).split(";") if s and s.strip()
            ]:
                await conn.execute(sa_text(statement))
        await conn.execute(
            sa_text(
                "CREATE TABLE extras.composite (a INTEGER NOT NULL, b INTEGER NOT NULL, "
                "PRIMARY KEY (a, b));"
            )
        )
        await conn.execute(sa_text("CREATE TABLE extras.nopk (v INTEGER);"))
        await conn.execute(
            sa_text("CREATE TABLE extras.intpk (id INTEGER PRIMARY KEY, name VARCHAR(50));")
        )
    yield
    async with db_engine.begin() as conn:
        await conn.execute(sa_text("DROP SCHEMA IF EXISTS extras CASCADE"))
        await conn.execute(sa_text("DROP SCHEMA IF EXISTS extras_seed CASCADE"))


# ── Engine CRUD + type mapping ───────────────────────
async def test_engine_crud_and_type_mapping(extras_schemas, session_factory):
    async with session_factory() as db:
        created = await create_row(
            db,
            "extras",
            "kitchen_sink",
            {
                "name": "Acme",
                "email": "acme@example.com",
                "description": "hello",
                "quantity": 3,
                "price": 9.99,
                "is_active": True,
                "due_date": date(2026, 1, 15),
                "extra_json": {"x": 1},
            },
        )
        assert created["name"] == "Acme"
        assert created["quantity"] == 3
        assert float(created["price"]) == 9.99
        assert isinstance(created["is_active"], bool)
        assert created["extra_json"] == {"x": 1}
        row_id = created["id"]

        # Pagination clamping
        page = await list_rows(db, "extras", "kitchen_sink", page=1, page_size=0)
        assert page["page_size"] == 1
        assert page["page"] == 1
        page2 = await list_rows(db, "extras", "kitchen_sink", page=1, page_size=500)
        assert page2["page_size"] == 100
        assert page2["total"] == 1

        # Filters (matching + skipped empty)
        assert (await list_rows(db, "extras", "kitchen_sink", filters={"name": "Acme"}))[
            "total"
        ] == 1
        assert (await list_rows(db, "extras", "kitchen_sink", filters={"name": None, "email": ""}))[
            "total"
        ] == 1

        got = await get_row(db, "extras", "kitchen_sink", row_id)
        assert got["id"] == row_id
        assert got["due_date"] == "2026-01-15"

        upd = await update_row(db, "extras", "kitchen_sink", row_id, {"price": 12.50})
        assert upd["price"] == 12.5

        await delete_row(db, "extras", "kitchen_sink", row_id)
        with pytest.raises(HTTPException) as exc:
            await get_row(db, "extras", "kitchen_sink", row_id)
        assert exc.value.status_code == 404


async def test_engine_validation_and_not_found(extras_schemas, session_factory):
    async with session_factory() as db:
        # Missing table → 404
        with pytest.raises(HTTPException) as exc:
            await resolve_table(db, "extras", "missing_table")
        assert exc.value.status_code == 404

        # No PK / composite PK → 400
        with pytest.raises(HTTPException) as exc:
            await get_row(db, "extras", "nopk", "1")
        assert exc.value.status_code == 400
        with pytest.raises(HTTPException) as exc:
            await get_row(db, "extras", "composite", "1-2")
        assert exc.value.status_code == 400

        # Invalid integer id → 400; invalid uuid id → 400
        with pytest.raises(HTTPException) as exc:
            await get_row(db, "extras", "intpk", "not-an-int")
        assert exc.value.status_code == 400
        with pytest.raises(HTTPException, match="Invalid UUID"):
            await get_row(db, "extras", "kitchen_sink", "not-a-uuid")

        # Unknown-but-valid uuid → 404 on get/update/delete
        missing_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(HTTPException) as exc:
            await get_row(db, "extras", "kitchen_sink", missing_id)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            await update_row(db, "extras", "kitchen_sink", missing_id, {"name": "X"})
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            await delete_row(db, "extras", "kitchen_sink", missing_id)
        assert exc.value.status_code == 404


async def test_engine_update_clears_fields_with_null(extras_schemas, session_factory):
    async with session_factory() as db:
        row = await create_row(
            db,
            "extras",
            "kitchen_sink",
            {"name": "Keep", "email": "k@example.com", "quantity": 1, "is_active": True},
        )
        clear = await update_row(
            db, "extras", "kitchen_sink", row["id"], {"description": None, "price": None}
        )
        assert clear["id"] == row["id"]
        assert clear["description"] is None
        assert clear["price"] is None
        assert clear["name"] == "Keep"  # untouched fields preserved


# ── Schema provisioner ───────────────────────────────
def test_sanitize_schema_name():
    assert _sanitize_schema_name("Work--able 123!") == "workable123"
    assert _sanitize_schema_name("!!!") == "workable_default"


def test_assign_entities_to_modules():
    tables = ["leads", "clients", "projects", "lead_history"]
    modules = [{"module": "crm"}, {"module": "project_management"}]
    out = _assign_entities_to_modules(tables, modules)
    crm = next(m for m in out if m["module"] == "crm")
    assert "leads" in crm["entities"]
    assert "projects" not in crm["entities"]
    # Keyword fallthrough: lead_history matches crm via keyword 'lead'
    assert "lead_history" in crm["entities"]

    # Explicit entities mapping takes priority
    out2 = _assign_entities_to_modules(
        ["customers"], [{"module": "crm", "entities": ["customers"]}]
    )
    assert out2[0]["entities"] == ["customers"]

    # No modules → single default module
    assert _assign_entities_to_modules(["a", "b"], [])[0]["module"] == "default"


def test_extract_schema_artifacts_missing():
    class FakeSolution:
        ai_state = {"generated_schema": "not-a-dict"}

    assert _extract_schema_artifacts(FakeSolution()) == (None, {})


async def test_provision_error_and_idempotent(workspace_solution, session_factory):
    sol_id = workspace_solution["solution_id"]
    async with session_factory() as db:
        sol = await db.get(Solution, sol_id)
        sol.ai_state = {}
        await db.flush()

        with pytest.raises(ValueError, match="no generated schema"):
            await provision_workable_schema(db, sol)

        # Second call returns the existing error record (idempotent).
        record = await provision_workable_schema(db, sol)
        assert record.status == "error"
        assert record.schema_name.startswith("workable_")


async def test_provision_success(workspace_solution, session_factory):
    sol_id = workspace_solution["solution_id"]
    from app.core.database import engine

    try:
        async with session_factory() as db:
            sol = await db.get(Solution, sol_id)
            sol.ai_state = {
                "generated_schema": {
                    "content": {"ddl": _KITCHEN_DDL.replace("{schema_name}.", "")}
                },
                "workable_modules": [
                    {"module": "kitchen", "path": "/kitchen", "entities": ["kitchen_sink"]}
                ],
            }
            await db.flush()
            record = await provision_workable_schema(db, sol)
            assert record.status == "provisioned"
            modules = {m["module"]: m for m in record.modules}
            assert "kitchen_sink" in modules["kitchen"]["entities"]
            schema_name = record.schema_name
    finally:
        async with engine.begin() as conn:
            await conn.execute(sa_text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))


# ── Synthetic data generator ─────────────────────────
async def test_seed_empty_schema(db_engine, session_factory):
    async with db_engine.begin() as conn:
        await conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS empty_seed"))
    async with session_factory() as db:
        assert await seed_synthetic_rows(db, "empty_seed", []) == 0
    async with db_engine.begin() as conn:
        await conn.execute(sa_text("DROP SCHEMA empty_seed CASCADE"))


async def test_seed_populates_tables_with_fk(extras_schemas, session_factory):
    async with session_factory() as db:
        created = await seed_synthetic_rows(
            db,
            "extras_seed",
            [{"module": "kitchen", "entities": ["kitchen_sink"]}],
            rows_per_table=3,
        )
        assert created >= 6  # kitchen_sink + child, 3 rows each
        total = (
            await db.execute(sa_text("SELECT count(*) FROM extras_seed.kitchen_sink"))
        ).scalar()
        assert total == 3
        fk_matched = (
            await db.execute(
                sa_text(
                    "SELECT count(*) FROM extras_seed.child c "
                    "JOIN extras_seed.kitchen_sink k ON c.parent_id = k.id"
                )
            )
        ).scalar()
        assert fk_matched == 3


# ── LLM provider layer ───────────────────────────────
async def test_mock_provider_returns_node_json():
    llm = get_llm(provider="mock", temperature=0.1, max_tokens=100)
    msg = await llm.ainvoke([SystemMessage(content="Business Analyst Agent role")])
    assert json.loads(msg.content)["confidence_score"] == 0.9

    # Unknown marker → generic payload
    msg2 = await llm.ainvoke([HumanMessage(content="hello")])
    assert json.loads(msg2.content)["content"] == "Mock response"


def test_mock_process_intelligence_state_driven():
    payload = _mock_process_intelligence(
        {"confirmed_modules": ["crm", "invoicing"], "identified_solutions": []}
    )
    assert payload["bpmn"]["name"] == "Core Business Process"
    assert len(payload["react_flow"]["nodes"]) == 4  # start + 2 tasks + end


def test_mock_content_builder_dispatch():
    payload = json.loads(
        _build_mock_content([SystemMessage(content="Full-Stack Code Synthesizer Agent")], {})
    )
    assert "generated_schema" in payload
    assert "workable_modules" in payload


async def test_get_llm_falls_back_to_mock_when_key_missing(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings.LLM_PROVIDER", "groq")
    monkeypatch.setattr("app.core.llm.settings.GROQ_API_KEY", "")
    llm = get_llm()
    assert isinstance(llm, MockChatModel)


def test_get_llm_real_provider_instantiation(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings.LLM_PROVIDER", "groq")
    monkeypatch.setattr("app.core.llm.settings.GROQ_API_KEY", "dummy-key")
    llm = get_llm()
    assert type(llm).__name__ == "ChatGroq"

    monkeypatch.setattr("app.core.llm.settings.LLM_PROVIDER", "openai")
    monkeypatch.setattr("app.core.llm.settings.OPENAI_API_KEY", "sk-dummy")
    llm = get_llm()
    assert type(llm).__name__ == "ChatOpenAI"


def test_has_llm_credentials(monkeypatch):
    monkeypatch.setattr("app.core.llm.settings.LLM_PROVIDER", "groq")
    monkeypatch.setattr("app.core.llm.settings.GROQ_API_KEY", "")
    assert has_llm_credentials() is False
    monkeypatch.setattr("app.core.llm.settings.GROQ_API_KEY", "key")
    assert has_llm_credentials() is True
    monkeypatch.setattr("app.core.llm.settings.LLM_PROVIDER", "mock")
    assert has_llm_credentials() is True
