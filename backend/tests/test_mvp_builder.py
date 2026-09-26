"""Unit tests for the OpenCode MVP Builder service.

Covers prompt assembly, workspace + file-tree helpers, config overlays,
networking against a mocked OpenCode sidecar, and end-to-end `run_build`.
"""

import zipfile
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Response

from app.core.config import settings
from app.services import mvp_builder as builder
from app.services import templates


def _sample_ai_state(**overrides) -> dict:
    state = {
        "business_description": "A training marketplace for enterprises",
        "industry": "edtech",
        "identified_solutions": ["catalog", "bookings"],
        "confirmed_modules": ["catalog", "bookings"],
        "solution_title": "Training Hub",
        "hld": {
            "content": {"system_overview": "Microservices on K8s", "components": [{"name": "api"}]}
        },
        "lld": {"content": {"modules": [{"name": "catalog", "endpoints": []}]}},
        "er_diagram": {
            "content": {
                "entities": [{"name": "courses", "fields": [{"name": "title", "type": "VARCHAR"}]}],
                "relationships": [],
            }
        },
        "api_spec": {"content": {"endpoints": [{"method": "GET", "path": "/api/v1/courses"}]}},
        "generated_schema": {"content": {"ddl": "CREATE TABLE courses (id UUID PRIMARY KEY);"}},
        "wireframes": [{"content": {"screens": [{"name": "Catalog"}]}}],
    }
    state.update(overrides)
    return state


def _make_client(handler: Callable) -> Callable:
    # The real call site passes base_url/timeout/headers, so the factory has to
    # tolerate whatever kwargs it is given rather than a fixed zero-arg shape.
    def _client(*_args: object, **_kwargs: object):
        return AsyncClient(
            transport=MockTransport(handler), base_url="http://opencodetest", timeout=30.0
        )

    return _client


async def _true() -> bool:
    return True


# ── Prompt assembly ──────────────────────────────────


def test_build_mvp_prompt_contains_artifacts():
    prompt = builder.build_mvp_prompt(_sample_ai_state(), "abc123def456/build_1")
    assert "Training Hub" in prompt
    assert "edtech" in prompt
    assert "catalog" in prompt
    assert "bookings" in prompt
    assert "CREATE TABLE courses" in prompt
    assert "abc123def456/build_1" in prompt
    assert "Do NOT rewrite the scaffold" in prompt
    assert "MVP Slot-Fill Request" in prompt
    assert "__MODEL_INSERTION_POINT__" in prompt
    assert "__ROUTER_INSERTION_POINT__" in prompt


def test_build_mvp_prompt_app_title_override():
    prompt = builder.build_mvp_prompt(_sample_ai_state(), "dir/build_1", app_title="Custom App")
    assert "**App:** Custom App" in prompt


def test_build_mvp_prompt_ddl_fallback_to_database_schema():
    state = _sample_ai_state(generated_schema=None)
    state["database_schema"] = {"content": {"ddl": "CREATE TABLE fallback (id INT);"}}
    prompt = builder.build_mvp_prompt(state, "dir/build_1")
    assert "CREATE TABLE fallback (id INT);" in prompt


def test_build_mvp_prompt_no_ddl_dumps_schema_json():
    state = _sample_ai_state(generated_schema=None)
    state["database_schema"] = {"content": {"tables": [{"name": "t1"}]}, "ddl": ""}
    prompt = builder.build_mvp_prompt(state, "dir/build_1")
    assert "t1" in prompt


# ── Workspace / file tree helpers ────────────────────


def test_workspace_root_creates_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MVP_BUILD_DIR", str(tmp_path / "mvp"))
    root = builder.workspace_root()
    assert root == (tmp_path / "mvp").resolve()
    assert root.exists()


def test_build_workspace_dir_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MVP_BUILD_DIR", str(tmp_path / "mvp"))
    sid = uuid4()
    build_dir = builder.build_workspace_dir(sid, 2)
    assert build_dir.name == "build_2"
    assert build_dir.parent.name == sid.hex[:12]
    assert build_dir.exists()
    assert builder._container_target(sid, 2) == f"{sid.hex[:12]}/build_2"


def test_list_build_files_excludes_noise(tmp_path):
    root = Path(tmp_path)
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("x", encoding="utf-8")
    (root / "node_modules" / "dep").mkdir(parents=True)
    (root / "node_modules" / "dep" / "index.js").write_text("y", encoding="utf-8")
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config").write_text("z", encoding="utf-8")
    (root / "dist").mkdir(parents=True)
    (root / "dist" / "bundle.js").write_text("b", encoding="utf-8")

    files = builder.list_build_files(root)
    paths = [str(p.relative_to(root)).replace("\\", "/") for p in files]
    assert "app/main.py" in paths
    assert all("node_modules" not in p for p in paths)
    assert all(".git" not in p for p in paths)
    assert all("dist" not in p for p in paths)


# ── Template scaffold ──────────────────────────────


def test_template_root_exists():
    root = builder.template_root()
    assert root.is_dir()
    assert (root / "backend" / "main.py").exists()
    assert (root / "frontend" / "package.json").exists()
    assert (root / "infra" / "render.yaml").exists()


def test_slugify():
    assert builder._slugify("FeedbackHub") == "feedbackhub"
    assert builder._slugify("My Cool App!") == "my-cool-app"


def test_scaffold_build_copies_and_substitutes(tmp_path):
    build_dir = tmp_path / "project"
    builder.scaffold_build(build_dir, app_title="Training Hub", inject_modules=["catalog"])

    # Core scaffold copied.
    assert (build_dir / "backend" / "main.py").exists()
    assert (build_dir / "frontend" / "src" / "app" / "page.tsx").exists()
    assert (build_dir / "infra" / "docker-compose.yml").exists()
    assert (build_dir / "infra" / "render.yaml").exists()

    # Deterministic placeholders substituted.
    assert "__APP_TITLE__" not in (build_dir / "backend" / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "Training Hub" in (build_dir / "frontend" / "src" / "app" / "layout.tsx").read_text(
        encoding="utf-8"
    )
    assert "training-hub" in (build_dir / "infra" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    # No leftover token in any substituted text file.
    remaining = [
        str(p.relative_to(build_dir))
        for p in build_dir.rglob("*")
        if p.is_file() and "__APP_" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert remaining == []


def test_scaffold_build_with_ai_agent_state(tmp_path):
    build_dir = tmp_path / "agent_project"
    agent_state = {
        "solution_title": "AutoAgent Pro",
        "industry": "ai_agents",
        "confirmed_modules": ["agents", "tools", "conversations"],
        "er_diagram": {
            "content": {
                "entities": [
                    {
                        "name": "agents",
                        "fields": [
                            {"name": "name", "type": "VARCHAR(255)"},
                            {"name": "system_prompt", "type": "TEXT"},
                            {"name": "model", "type": "VARCHAR(100)"},
                            {"name": "temperature", "type": "FLOAT"},
                            {"name": "is_active", "type": "BOOLEAN"},
                        ],
                    },
                    {
                        "name": "tools",
                        "fields": [
                            {"name": "name", "type": "VARCHAR(255)"},
                            {"name": "description", "type": "TEXT"},
                        ],
                    },
                ]
            }
        },
    }
    builder.scaffold_build(
        build_dir,
        app_title="AutoAgent Pro",
        inject_modules=["agents", "tools"],
        ai_state=agent_state,
    )

    models_code = (build_dir / "backend" / "models.py").read_text(encoding="utf-8")
    assert "class Agents(Base):" in models_code
    assert "system_prompt: Mapped[str] = mapped_column(Text" in models_code
    assert "temperature: Mapped[float] = mapped_column(Float" in models_code
    assert "is_active: Mapped[bool] = mapped_column(Boolean" in models_code

    schemas_code = (build_dir / "backend" / "schemas.py").read_text(encoding="utf-8")
    assert "class AgentsBase(BaseModel):" in schemas_code
    assert "system_prompt: str" in schemas_code
    assert "temperature: float" in schemas_code

    routers_code = (build_dir / "backend" / "routers.py").read_text(encoding="utf-8")
    assert "/agents/{agent_id}/run" in routers_code

    # Agent runner service should be generated
    assert (build_dir / "backend" / "agent_runner.py").exists()

    # Frontend module pages should be generated
    assert (build_dir / "frontend" / "src" / "app" / "agents" / "page.tsx").exists()
    assert (build_dir / "frontend" / "src" / "app" / "tools" / "page.tsx").exists()

    agents_page = (build_dir / "frontend" / "src" / "app" / "agents" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Interactive Agent Playground" in agents_page


def test_package_build_zips_project(tmp_path):
    root = Path(tmp_path)
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("print(1)", encoding="utf-8")
    (root / "README.md").write_text("# MVP", encoding="utf-8")

    buffer = builder.package_build(root)
    with zipfile.ZipFile(buffer) as zf:
        names = set(zf.namelist())
    assert "backend/main.py" in names
    assert "README.md" in names


def test_package_build_missing_dir_raises(tmp_path):
    with pytest.raises(builder.MVPBuilderError):
        builder.package_build(tmp_path / "nope")


def test_apply_config_overlay_writes_env_and_readme(tmp_path):
    root = Path(tmp_path)
    (root / "README.md").write_text("# Old Title\n\nbody", encoding="utf-8")

    overlay = builder.apply_config_overlay(root, "My Cool App", {"DATABASE_URL": "postgres://x"})

    assert overlay == {"app_name": "My Cool App", "DATABASE_URL": "postgres://x"}
    assert (root / ".env.local").exists()
    assert "DATABASE_URL=postgres://x" in (root / ".env.local").read_text(encoding="utf-8")
    config = (root / ".config" / "app_config.json").read_text(encoding="utf-8")
    assert '"app_name": "My Cool App"' in config
    assert (root / "README.md").read_text(encoding="utf-8").startswith("# My Cool App")


def test_apply_config_overlay_missing_dir_raises(tmp_path):
    with pytest.raises(builder.MVPBuilderError):
        builder.apply_config_overlay(tmp_path / "nope", "App", {})


def test_cleanup_build_removes_workspace(tmp_path):
    project = tmp_path / "abc" / "build_1"
    project.mkdir(parents=True)
    (project / "file.txt").write_text("hi", encoding="utf-8")
    builder.cleanup_build(project)
    assert not project.exists()


# ── OpenCode sidecar networking (mocked) ─────────────


def test_auth_headers_have_no_auth():
    assert "Authorization" not in builder._auth_headers()


@pytest.mark.asyncio
async def test_health_ok(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(200, json={"healthy": True, "version": "x"})

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    assert await builder.health() is True


@pytest.mark.asyncio
async def test_health_down(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(500, json={})

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    assert await builder.health() is False


@pytest.mark.asyncio
async def test_health_network_error(monkeypatch):
    def _client():
        async def handler(request: httpx.Request) -> Response:
            raise httpx.ConnectError("boom")

        return AsyncClient(transport=MockTransport(handler), base_url="http://x", timeout=10.0)

    monkeypatch.setattr(builder, "_client", _client)
    assert await builder.health() is False


@pytest.mark.asyncio
async def test_create_session_ok(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        assert request.url.path == "/session"
        return Response(200, json={"id": "sess-1"})

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    assert await builder.create_session("MVP") == "sess-1"


@pytest.mark.asyncio
async def test_create_session_missing_id(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(200, json={"title": "MVP"})

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    with pytest.raises(builder.MVPBuilderError):
        await builder.create_session("MVP")


@pytest.mark.asyncio
async def test_create_session_500(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(500, text="boom")

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    with pytest.raises(builder.MVPBuilderError):
        await builder.create_session("MVP")


@pytest.mark.asyncio
async def test_send_build_prompt_ok(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        assert request.url.path == "/session/sess-1/message"
        return Response(200, json={"info": {"error": None}, "parts": []})

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    result = await builder.send_build_prompt("sess-1", "build it")
    assert result["info"]["error"] is None


@pytest.mark.asyncio
async def test_send_build_prompt_400(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(400, text="bad")

    monkeypatch.setattr(builder, "_client", _make_client(handler))
    with pytest.raises(builder.MVPBuilderError):
        await builder.send_build_prompt("sess-1", "build it")


@pytest.mark.asyncio
async def test_abort_session_tolerates_failure(monkeypatch):
    def _client():
        async def handler(request: httpx.Request) -> Response:
            raise httpx.ConnectError("down")

        return AsyncClient(transport=MockTransport(handler), base_url="http://x", timeout=10.0)

    monkeypatch.setattr(builder, "_client", _client)
    await builder.abort_session("sess-bad")  # must not raise


# ── run_build orchestration ────────────────────────


@pytest.mark.asyncio
async def test_run_build_success(monkeypatch, tmp_path):
    async def _sess(t):
        return "sess-1"

    async def _send(sid, p):
        return {"info": {"error": None}}

    def _scaffold(build_dir, *, app_title, inject_modules, **kwargs):
        Path(build_dir).mkdir(parents=True, exist_ok=True)

    verified_calls = []

    async def _mock_verify(workspace_dir, **kwargs):
        verified_calls.append(workspace_dir)
        return []

    monkeypatch.setattr(settings, "MVP_BUILD_DIR", str(tmp_path))
    monkeypatch.setattr(builder, "health", _true)
    monkeypatch.setattr(builder, "create_session", _sess)
    monkeypatch.setattr(builder, "send_build_prompt", _send)
    monkeypatch.setattr(builder, "scaffold_build", _scaffold)
    monkeypatch.setattr("app.services.mvp_verifier.verify_and_repair", _mock_verify)

    sid = uuid4()
    # Pre-create a file in the agreed workspace to simulate sidecar output.
    target = builder.build_workspace_dir(sid, 1)
    (target / "README.md").write_text("# Built", encoding="utf-8")

    result = await builder.run_build(sid, _sample_ai_state(), 1, title="Training Hub")
    assert result["session_id"] == "sess-1"
    assert result["file_count"] == 1
    assert result["files"] == ["README.md"]
    assert len(verified_calls) == 1
    assert verified_calls[0] == target


@pytest.mark.asyncio
async def test_run_build_sidecar_down(monkeypatch):
    async def _down():
        return False

    monkeypatch.setattr(builder, "health", _down)
    with pytest.raises(builder.MVPBuilderError):
        await builder.run_build(uuid4(), _sample_ai_state(), 1)


@pytest.mark.asyncio
async def test_run_build_aborts_on_prompt_failure(monkeypatch, tmp_path):
    async def _sess(t):
        return "sess-1"

    async def _boom(sid, p):
        raise builder.MVPBuilderError("prompt failed")

    calls: list[str] = []

    async def _abort(sid):
        calls.append(sid)

    monkeypatch.setattr(settings, "MVP_BUILD_DIR", str(tmp_path))
    monkeypatch.setattr(builder, "health", _true)
    monkeypatch.setattr(builder, "create_session", _sess)
    monkeypatch.setattr(builder, "send_build_prompt", _boom)
    monkeypatch.setattr(builder, "abort_session", _abort)
    monkeypatch.setattr(
        builder, "scaffold_build", lambda build_dir, *, app_title, inject_modules, **kwargs: None
    )

    with pytest.raises(builder.MVPBuilderError):
        await builder.run_build(uuid4(), _sample_ai_state(), 1)
    assert calls == ["sess-1"]


# ── Starter templates ──────────────────────────────


def test_list_templates_has_small_presets():
    presets = templates.list_templates()
    slugs = {p["slug"] for p in presets}
    assert {"todo", "calculator", "portfolio"} <= slugs
    for p in presets:
        assert p["title"]
        assert p["app_name"]
        assert p["industry"]


def test_get_template_returns_deep_copy():
    tpl = templates.get_template("todo")
    assert tpl is not None
    first = tpl.build_ai_state()
    second = tpl.build_ai_state()
    assert first == second
    assert first is not second
    assert "task_management" in first["confirmed_modules"]
    assert first["generated_schema"]["content"]["ddl"].startswith("CREATE TABLE project")


def test_get_template_unknown_returns_none():
    assert templates.get_template("nope") is None


def test_todo_template_prompt_small_enough_for_generous_tpm():
    tpl = templates.get_template("todo")
    prompt = builder.build_mvp_prompt(tpl.build_ai_state(), "012345abcdef/build_1")  # type: ignore[arg-type]
    assert len(prompt) < 3000
    assert "task_management" in prompt


def test_restaurant_template_registered_and_builds_state():
    tpl = templates.get_template("restaurant_ordering")
    assert tpl is not None
    assert tpl.slug == "restaurant_ordering"
    state = tpl.build_ai_state()
    assert "dishes" in state["confirmed_modules"]
    assert "orders" in state["confirmed_modules"]


def test_apply_restaurant_template_files(tmp_path):
    builder.scaffold_build(
        tmp_path, app_title="Bistro Demo", inject_modules=["restaurant_ordering"]
    )
    templates.apply_template_files(tmp_path, "restaurant_ordering", app_title="Bistro Demo")

    # Backend verification
    models = (tmp_path / "backend" / "models.py").read_text(encoding="utf-8")
    assert "class Dish(Base):" in models
    assert "class Order(Base):" in models

    schemas = (tmp_path / "backend" / "schemas.py").read_text(encoding="utf-8")
    assert "class DishCreate(DishBase):" in schemas
    assert "class OrderRead(OrderBase):" in schemas

    routers = (tmp_path / "backend" / "routers.py").read_text(encoding="utf-8")
    assert "/dishes" in routers
    assert "/orders" in routers
    assert "Truffle Mushroom Risotto" in routers

    # Frontend verification
    page_tsx = (tmp_path / "frontend" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "Digital Menu & Table Ordering System" in page_tsx
    assert "Bistro Demo" in page_tsx

    orders_page = (tmp_path / "frontend" / "src" / "app" / "orders" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Kitchen Display" in orders_page
    assert "Orders Board" in orders_page

    dishes_page = (tmp_path / "frontend" / "src" / "app" / "dishes" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Dish &amp; Menu Management" in dishes_page


def test_scaffold_build_with_restaurant_ai_state(tmp_path):
    build_dir = tmp_path / "restaurant_project"
    restaurant_state = {
        "solution_title": "Grand Cafe",
        "description": "An online menu and food ordering system with admin kitchen orders",
        "confirmed_modules": ["dishes", "orders"],
        "er_diagram": {
            "content": {
                "entities": [
                    {
                        "name": "dishes",
                        "fields": [
                            {"name": "name", "type": "VARCHAR(255)"},
                            {"name": "price", "type": "FLOAT"},
                            {"name": "category", "type": "VARCHAR(100)"},
                        ],
                    },
                    {
                        "name": "orders",
                        "fields": [
                            {"name": "table_number", "type": "VARCHAR(50)"},
                            {"name": "total_amount", "type": "FLOAT"},
                            {"name": "status", "type": "VARCHAR(50)"},
                        ],
                    },
                ]
            }
        },
    }

    builder.scaffold_build(
        build_dir,
        app_title="Grand Cafe",
        inject_modules=["dishes", "orders"],
        ai_state=restaurant_state,
    )

    page_content = (build_dir / "frontend" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "Digital Menu & Table Ordering System" in page_content
    assert "Grand Cafe" in page_content

    # Orders and dishes routes should be created
    assert (build_dir / "frontend" / "src" / "app" / "orders" / "page.tsx").exists()
    assert (build_dir / "frontend" / "src" / "app" / "dishes" / "page.tsx").exists()


def test_scaffold_build_with_gym_fitness_ai_state(tmp_path):
    build_dir = tmp_path / "gym_project"
    gym_state = {
        "solution_title": "Apex Performance Club",
        "description": "A high-intensity fitness club with class booking and member attendance tracking",
        "industry": "fitness",
        "confirmed_modules": ["workouts", "bookings"],
        "er_diagram": {
            "content": {
                "entities": [
                    {
                        "name": "workouts",
                        "fields": [
                            {"name": "name", "type": "VARCHAR(255)"},
                            {"name": "price", "type": "FLOAT"},
                            {"name": "category", "type": "VARCHAR(100)"},
                        ],
                    },
                    {
                        "name": "bookings",
                        "fields": [
                            {"name": "member_name", "type": "VARCHAR(100)"},
                            {"name": "total_amount", "type": "FLOAT"},
                            {"name": "status", "type": "VARCHAR(50)"},
                        ],
                    },
                ]
            }
        },
    }

    builder.scaffold_build(
        build_dir,
        app_title="Apex Performance Club",
        inject_modules=["workouts", "bookings"],
        ai_state=gym_state,
    )

    page_content = (build_dir / "frontend" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "Apex Performance Club" in page_content
    assert "Class Scheduling & Member Pass Management" in page_content
    assert "Browse Schedule" in page_content
    assert "Member Bookings" in page_content
    assert "Book Class" in page_content
    assert "Class Reservations" in page_content

    # Workout and bookings studios should be created
    assert (build_dir / "frontend" / "src" / "app" / "workouts" / "page.tsx").exists()
    assert (build_dir / "frontend" / "src" / "app" / "bookings" / "page.tsx").exists()
