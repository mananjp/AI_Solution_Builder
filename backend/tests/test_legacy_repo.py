"""
AI Solution Builder — Tests for Legacy Repository Modernization Suite

Verifies:
- Strict sutra_os boundary protection guardrail
- Stack, entry points, debt, and asset discovery
- Credential validation and secure masking
- Conflict-graph parallel task execution with file serialization
- AI Chatbot feature extension into existing architecture
- End-to-end modernization & report integrity
"""

import asyncio
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.legacy_repo.analyzer import LegacyRepoAnalyzer
from app.services.legacy_repo.boundary import (
    ScopeBoundaryViolation,
    assert_safe_boundary,
    is_path_safe,
)
from app.services.legacy_repo.conflict_graph import ConflictGraphScheduler, TaskWorkstream
from app.services.legacy_repo.credentials import CredentialValidator, mask_secret
from app.services.legacy_repo.feature_extension import FeatureExtensionEngine
from app.services.legacy_repo.modernizer import LegacyRepoModernizer
from app.services.legacy_repo.validator import LegacyRepoValidator
from main import app


@pytest.fixture
def sample_legacy_repo(tmp_path: Path) -> Path:
    """Create a realistic mock legacy repository with technical debt, assets, and existing features."""
    repo = tmp_path / "legacy_crm_app"
    repo.mkdir()

    # 1. Manifest with outdated dependencies
    pkg_data = {
        "name": "legacy-crm-app",
        "version": "1.0.0",
        "dependencies": {
            "react": "16.8.0",
            "express": "4.16.0",
            "request": "^2.88.2",
            "moment": "^2.29.1",
        },
        "devDependencies": {
            "webpack": "^4.44.0",
        },
    }
    (repo / "package.json").write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

    # 2. Existing backend entry point (Feature A: Customers API)
    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "server.js").write_text(
        "var express = require('express');\nvar app = express();\n"
        "app.get('/api/customers', function(req, res) { res.json([{ id: 1, name: 'Acme Corp' }]); });\n"
        "app.listen(3000);\n",
        encoding="utf-8",
    )

    # 3. Existing frontend entry point (Feature B: Dashboard)
    (src_dir / "App.jsx").write_text(
        "import React from 'react';\n"
        "export default function App() {\n"
        "  return <div className='dashboard'><h1>Customer CRM Dashboard</h1></div>;\n"
        "}\n",
        encoding="utf-8",
    )

    # 4. Existing branding assets (Logos and Icons)
    assets_dir = repo / "public" / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand_logo.svg").write_text("<svg><circle r='10'/></svg>", encoding="utf-8")
    (assets_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")

    # 5. Existing env file with potential secret
    (repo / ".env").write_text("DATABASE_URL=postgres://user:pass@localhost:5432/crm_db\nPORT=3000\n", encoding="utf-8")

    return repo


# ── 1. Boundary & sutra_os Protection Tests ──────────────────────────────────


def test_sutra_os_strict_boundary_protection():
    """Verify that any path touching or referencing sutra_os is unconditionally rejected."""
    # Absolute sutra_os path
    assert not is_path_safe("sutra_os")
    assert not is_path_safe("d:/Project/AI_Solution_Builder/sutra_os")
    assert not is_path_safe("d:/Project/AI_Solution_Builder/sutra_os/lib/main.dart")
    assert not is_path_safe("relative/path/to/sutra_os/anything")

    with pytest.raises(ScopeBoundaryViolation) as excinfo:
        assert_safe_boundary("d:/Project/AI_Solution_Builder/sutra_os", action="inspect")
    assert "ABSOLUTE SCOPE RESTRICTION" in str(excinfo.value)
    assert "sutra_os" in str(excinfo.value)

    with pytest.raises(ScopeBoundaryViolation):
        assert_safe_boundary("sutra_os/some_file.dart", action="modify")


def test_safe_paths_allowed(tmp_path: Path):
    """Verify safe paths outside sutra_os are permitted."""
    safe = tmp_path / "my_project"
    safe.mkdir()
    res = assert_safe_boundary(safe, action="read")
    assert res == safe.resolve()


# ── 2. Credential Validation & Masking Tests ─────────────────────────────────


def test_credential_masking():
    """Verify secrets are masked into ••••••••••••abcd format."""
    assert mask_secret("gsk_test_secret_key_1234567890abcd") == "••••••••••••abcd"
    assert mask_secret("sk-1234567890abcdef") == "••••••••••••cdef"
    assert mask_secret("") == "••••"


def test_credential_format_validation():
    """Test format verification for major LLM providers."""
    # Groq API key format
    valid_groq = "gsk_" + "a" * 32
    ok, _ = CredentialValidator.validate_format("GROQ_API_KEY", valid_groq)
    assert ok

    bad_groq = "short_key"
    ok, msg = CredentialValidator.validate_format("GROQ_API_KEY", bad_groq)
    assert not ok

    # OpenAI key format
    valid_openai = "sk-" + "b" * 32
    ok, _ = CredentialValidator.validate_format("OPENAI_API_KEY", valid_openai)
    assert ok


def test_credential_workspace_persistence(tmp_path: Path):
    """Verify credentials are safely written to workspace .env without committing to git."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    creds = {"GROQ_API_KEY": "gsk_" + "x" * 32}
    updated = CredentialValidator.apply_to_workspace_env(ws, creds)
    assert "GROQ_API_KEY" in updated

    # Check .env
    env_content = (ws / ".env").read_text()
    assert creds["GROQ_API_KEY"] in env_content

    # Check .env.example (must NOT contain real key!)
    example_content = (ws / ".env.example").read_text()
    assert "your_groq_api_key_here" in example_content
    assert creds["GROQ_API_KEY"] not in example_content

    # Check .gitignore
    gi_content = (ws / ".gitignore").read_text()
    assert ".env" in gi_content


# ── 3. Read-Only Repository Analyzer Tests ───────────────────────────────────


def test_legacy_repo_analyzer(sample_legacy_repo: Path):
    """Test full static read-only inspection on legacy CRM codebase."""
    analyzer = LegacyRepoAnalyzer(sample_legacy_repo)
    report = analyzer.analyze()

    assert report["project_name"] == "legacy_crm_app"
    stack = report["technology_stack"]
    assert "JavaScript" in stack["languages"]
    assert "Express" in str(stack["backend_framework"])
    assert "React" in str(stack["frontend_framework"])

    # Outdated dependencies detected
    debt = report["technical_debt"]
    outdated_pkgs = {d["package"] for d in debt["outdated_dependencies"]}
    assert "request" in outdated_pkgs or "moment" in outdated_pkgs

    # Assets discovered for reuse
    assets = report["assets_inventory"]
    assert len(assets["logos"]) >= 1 or len(assets["icons"]) >= 1
    assert any("brand_logo.svg" in x for x in assets["logos"] + assets["images"])

    # Phased plan generated
    plan = report["modernization_plan"]
    assert len(plan) >= 4
    assert any("Security" in p["title"] for p in plan)
    assert any("Feature Extension" in p["title"] for p in plan)


# ── 4. Conflict-Graph Parallel Scheduler Tests ────────────────────────────────


@pytest.mark.asyncio
async def test_conflict_graph_scheduler():
    """Verify tasks on disjoint files run in parallel while tasks sharing files are serialized."""
    scheduler = ConflictGraphScheduler(max_concurrency=4)
    execution_order: list[str] = []

    async def task_a():
        execution_order.append("A_start")
        await asyncio.sleep(0.08)
        execution_order.append("A_end")
        return "A done"

    async def task_b():
        execution_order.append("B_start")
        await asyncio.sleep(0.08)
        execution_order.append("B_end")
        return "B done"

    async def task_c_conflicting_with_a():
        execution_order.append("C_start")
        await asyncio.sleep(0.02)
        execution_order.append("C_end")
        return "C done"

    # Task A and Task B have disjoint files: should run concurrently
    scheduler.add_task(
        TaskWorkstream(
            task_id="t_a",
            name="Task A",
            workstream="modernization",
            description="Edit package.json",
            files_to_modify=["package.json"],
            execute_fn=task_a,
        )
    )
    scheduler.add_task(
        TaskWorkstream(
            task_id="t_b",
            name="Task B",
            workstream="feature_extension",
            description="Edit AIChatbot.tsx",
            files_to_modify=["AIChatbot.tsx"],
            execute_fn=task_b,
        )
    )
    # Task C also needs package.json: must wait for Task A to finish!
    scheduler.add_task(
        TaskWorkstream(
            task_id="t_c",
            name="Task C",
            workstream="modernization",
            description="Also edit package.json",
            files_to_modify=["package.json"],
            execute_fn=task_c_conflicting_with_a,
        )
    )

    res = await scheduler.execute_all()
    assert res["completed"] == 3
    assert res["failed"] == 0

    # Verify that A and B started concurrently (both started before A finished)
    assert execution_order.index("A_start") < execution_order.index("A_end")
    assert execution_order.index("B_start") < execution_order.index("A_end")

    # Verify that C did NOT start until A finished (due to package.json file conflict)
    assert execution_order.index("C_start") > execution_order.index("A_end")


# ── 5. Feature Extension (AI Chatbot) Tests ───────────────────────────────────


def test_feature_extension_engine(sample_legacy_repo: Path):
    """Test injecting AI chatbot service and widget without disrupting existing code."""
    analyzer = LegacyRepoAnalyzer(sample_legacy_repo)
    analysis = analyzer.analyze()

    engine = FeatureExtensionEngine(
        sample_legacy_repo,
        analysis["technology_stack"],
        analysis["entry_points"],
    )

    modified = engine.add_ai_chatbot(provider="groq", model="llama-3.3-70b-versatile")
    assert len(modified) >= 2

    # Check chatbot widget file exists
    widget_file = sample_legacy_repo / "src" / "components" / "AIChatbotWidget.tsx"
    assert widget_file.exists()
    content = widget_file.read_text(encoding="utf-8")
    assert "Ask AI Assistant" in content

    # Check original files still intact (CRM feature A & B preserved)
    assert (sample_legacy_repo / "src" / "server.js").exists()
    assert "Acme Corp" in (sample_legacy_repo / "src" / "server.js").read_text()
    assert (sample_legacy_repo / "src" / "App.jsx").exists()


# ── 6. End-to-End Modernizer Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_repo_modernizer_e2e(sample_legacy_repo: Path):
    """Test complete modernization workflow from target directory to packaged ZIP."""
    modernizer = LegacyRepoModernizer(sample_legacy_repo, create_isolated_copy=True)
    report = await modernizer.modernize(
        requested_features=["ai_chatbot"],
        credentials={"GROQ_API_KEY": "gsk_" + "t" * 32},
    )

    assert report["status"] == "complete"
    assert report["sutra_os"] == "NOT MODIFIED (strictly preserved and untouched)"
    assert report["git"]["push"] == "None (No remote write)"
    assert len(report["modified_files"]) > 0
    assert report["validation"]["all_passed"] is True
    assert report["zip_size_bytes"] > 0
    assert Path(report["zip_path"]).exists()


# ── 7. FastAPI Endpoint Integration Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_repo_api_endpoints(sample_legacy_repo: Path):
    """Test /api/v1/legacy-repo HTTP endpoints."""
    import uuid
    from app.core.security import get_current_user
    from app.models.user import User

    mock_user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        org_id=uuid.uuid4(),
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock_token"}

            # 1. Test Boundary Rejection on sutra_os via API
            resp = await client.post(
                "/api/v1/legacy-repo/analyze",
                json={"local_path": "d:/Project/AI_Solution_Builder/sutra_os"},
                headers=headers,
            )
            assert resp.status_code == 403
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message") or err_body.get("detail", "")
            assert "ABSOLUTE SCOPE RESTRICTION" in err_msg

            # 2. Test Analyze on safe sample legacy repo
            resp = await client.post(
                "/api/v1/legacy-repo/analyze",
                json={"local_path": str(sample_legacy_repo)},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["project_name"] == "legacy_crm_app"
            assert "technology_stack" in data

            # 3. Test Validate Credentials
            val_resp = await client.post(
                "/api/v1/legacy-repo/validate-credentials",
                json={"key_name": "GROQ_API_KEY", "key_value": "gsk_" + "m" * 32},
                headers=headers,
            )
            assert val_resp.status_code == 200
            val_data = val_resp.json()
            assert val_data["format_valid"] is True
            assert val_data["masked_key"].startswith("••••")

            # 4. Test Modernize endpoint
            mod_resp = await client.post(
                "/api/v1/legacy-repo/modernize",
                json={
                    "local_path": str(sample_legacy_repo),
                    "requested_features": ["ai_chatbot"],
                    "credentials": {"GROQ_API_KEY": "gsk_" + "k" * 32},
                },
                headers=headers,
            )
            assert mod_resp.status_code == 200
            mod_data = mod_resp.json()
            assert mod_data["status"] == "complete"
            assert mod_data["sutra_os"] == "NOT MODIFIED (strictly preserved and untouched)"
    finally:
        app.dependency_overrides.clear()
