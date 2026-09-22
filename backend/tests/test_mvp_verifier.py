"""Tests for the MVP Build Verification & Bounded Repair Engine."""

from pathlib import Path

import pytest

from app.services.mvp_verifier import (
    VerificationError,
    verify_and_repair,
    verify_backend_integrity,
    verify_frontend_integrity,
    verify_python_syntax,
)


def test_verify_python_syntax_valid(tmp_path: Path):
    valid_file = tmp_path / "valid.py"
    valid_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")
    assert verify_python_syntax(valid_file) is None


def test_verify_python_syntax_invalid(tmp_path: Path):
    invalid_file = tmp_path / "invalid.py"
    invalid_file.write_text("def broken(\n    return 'unclosed'\n", encoding="utf-8")
    err = verify_python_syntax(invalid_file)
    assert err is not None
    assert "SyntaxError" in err


def test_verify_backend_integrity_missing_files(tmp_path: Path):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    errors = verify_backend_integrity(backend_dir)
    assert any("Missing required backend file: backend/main.py" in e for e in errors)
    assert any("Missing required backend file: backend/models.py" in e for e in errors)


def test_verify_backend_integrity_valid(tmp_path: Path):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (backend_dir / "models.py").write_text("class Item:\n    pass\n", encoding="utf-8")
    (backend_dir / "schemas.py").write_text("class ItemSchema:\n    pass\n", encoding="utf-8")
    (backend_dir / "routers.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8"
    )

    errors = verify_backend_integrity(backend_dir)
    assert errors == []


def test_verify_frontend_integrity_missing_package_json(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    errors = verify_frontend_integrity(frontend_dir)
    assert any("Missing required frontend file" in e for e in errors)


def test_verify_frontend_integrity_valid(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        '{"dependencies": {"next": "15.0.0"}}', encoding="utf-8"
    )
    app_dir = frontend_dir / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    errors = verify_frontend_integrity(frontend_dir)
    assert errors == []


@pytest.mark.asyncio
async def test_verify_and_repair_passes_cleanly(tmp_path: Path):
    # Setup complete workspace
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (backend / "models.py").write_text("class Item:\n    pass\n", encoding="utf-8")
    (backend / "schemas.py").write_text("class ItemSchema:\n    pass\n", encoding="utf-8")
    (backend / "routers.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8"
    )
    (backend / "tests").mkdir(exist_ok=True)
    (backend / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"dependencies": {"next": "15.0.0"}}', encoding="utf-8")
    app_dir = frontend / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    result = await verify_and_repair(tmp_path, session_id="test-sess", target_dir="test-target")
    assert result["verified"] is True
    assert result["repair_turns"] == 0


@pytest.mark.asyncio
async def test_verify_and_repair_successful_repair_turn(tmp_path: Path):
    # Workspace initially has a broken Python syntax file
    backend = tmp_path / "backend"
    backend.mkdir()
    broken_py = backend / "models.py"
    broken_py.write_text("class Broken:\n    def broken(\n", encoding="utf-8")
    (backend / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (backend / "schemas.py").write_text("class Item:\n    pass\n", encoding="utf-8")
    (backend / "routers.py").write_text("class Router:\n    pass\n", encoding="utf-8")
    (backend / "tests").mkdir(exist_ok=True)
    (backend / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"dependencies": {"next": "15.0.0"}}', encoding="utf-8")
    app_dir = frontend / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    # Mock send_prompt_fn that fixes the file during the repair turn
    repair_prompts = []

    async def fake_repair_prompt(sess_id: str, prompt: str):
        repair_prompts.append(prompt)
        # Fix the file
        broken_py.write_text("class Broken:\n    pass\n", encoding="utf-8")
        return {"info": "fixed"}

    result = await verify_and_repair(
        tmp_path,
        session_id="test-sess",
        target_dir="test-target",
        max_repair_turns=2,
        send_prompt_fn=fake_repair_prompt,
    )
    assert result["verified"] is True
    assert result["repair_turns"] == 1
    assert len(repair_prompts) == 1
    assert "SyntaxError" in repair_prompts[0]


@pytest.mark.asyncio
async def test_verify_and_repair_exhausted_budget(tmp_path: Path):
    # Broken workspace that never gets fixed
    backend = tmp_path / "backend"
    backend.mkdir()
    broken_py = backend / "models.py"
    broken_py.write_text("class Broken:\n    def broken(\n", encoding="utf-8")

    async def fake_failing_prompt(sess_id: str, prompt: str):
        return {"info": "tried but still broken"}

    with pytest.raises(VerificationError) as exc_info:
        await verify_and_repair(
            tmp_path,
            session_id="test-sess",
            target_dir="test-target",
            max_repair_turns=2,
            send_prompt_fn=fake_failing_prompt,
        )

    assert "Build verification failed after 2 repair attempt(s)" in str(exc_info.value)


def test_verify_frontend_npm_ordering_success(tmp_path: Path, monkeypatch):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        '{"dependencies": {"next": "15.0.0"}}', encoding="utf-8"
    )
    app_dir = frontend_dir / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    calls = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd[0:3])

        class FakeCompleted:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return FakeCompleted()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    errors = verify_frontend_integrity(frontend_dir, run_build=True)
    assert errors == []
    # Verify ordering: npm install must come before npm run build
    assert len(calls) == 2
    assert calls[0] == ["npm", "install", "--prefer-offline"]
    assert calls[1] == ["npm", "run", "build"]


def test_verify_frontend_npm_install_failure_stops_build(tmp_path: Path, monkeypatch):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        '{"dependencies": {"next": "15.0.0"}}', encoding="utf-8"
    )
    app_dir = frontend_dir / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    calls = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd[0:3])

        class FakeCompleted:
            returncode = 1
            stdout = ""
            stderr = "npm ERR! code ERESOLVE"

        return FakeCompleted()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    errors = verify_frontend_integrity(frontend_dir, run_build=True)
    assert len(errors) == 1
    assert "Frontend npm install failed" in errors[0]
    # Verify npm run build was NEVER called because install failed
    assert len(calls) == 1
    assert calls[0] == ["npm", "install", "--prefer-offline"]


def test_verify_frontend_npm_build_failure(tmp_path: Path, monkeypatch):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        '{"dependencies": {"next": "15.0.0"}}', encoding="utf-8"
    )
    app_dir = frontend_dir / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return <div>Home</div>; }", encoding="utf-8"
    )

    calls = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd[0:3])

        class FakeCompleted:
            returncode = 0 if "install" in cmd else 1
            stdout = ""
            stderr = "Error: Next.js build failed"

        return FakeCompleted()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    errors = verify_frontend_integrity(frontend_dir, run_build=True)
    assert len(errors) == 1
    assert "Frontend npm build failed" in errors[0]
    assert len(calls) == 2
