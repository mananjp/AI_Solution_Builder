"""Spec → deterministic codegen → behavioural verifier, end to end (no LLM)."""

import json
import shutil
from pathlib import Path

import pytest

from app.services.app_spec import AppSpec
from app.services.mvp_builder import template_root
from app.services.mvp_verifier import restore_locked, snapshot_locked, verify_workspace_report
from app.services.spec_codegen import tampered_files, write_generated

FIXTURE = Path(__file__).parent / "fixtures" / "spliteasy_spec.json"

BALANCES_IMPL = '''    if await session.get(models.Group, group_id) is None:
        raise HTTPException(404, "group not found")
    members = (await session.execute(select(models.Member).where(models.Member.group_id == group_id).order_by(models.Member.id))).scalars().all()
    rows = (await session.execute(select(models.Expense.paid_by_id, func.sum(models.Expense.amount)).where(models.Expense.group_id == group_id).group_by(models.Expense.paid_by_id))).all()
    paid = {pid: float(t) for pid, t in rows}
    total = round(sum(paid.values()), 2)
    share = total / len(members) if members else 0
    return {"total": total, "balances": [{"member_id": m.id, "balance": round(paid.get(m.id, 0) - share, 2)} for m in members]}'''


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    shutil.copytree(template_root(), tmp_path / "app")
    spec = AppSpec.model_validate(json.loads(FIXTURE.read_text()))
    write_generated(tmp_path / "app", spec)
    return tmp_path / "app"


def test_spec_rejects_untested_action():
    data = json.loads(FIXTURE.read_text())
    data["acceptance_tests"] = data["acceptance_tests"][:2] + [data["acceptance_tests"][0]]
    with pytest.raises(ValueError, match="actions without acceptance tests"):
        AppSpec.model_validate(data)


def test_stub_fails_then_real_logic_passes(workspace: Path):
    report = verify_workspace_report(workspace)
    assert report["tests"]["failed"] >= 1
    assert any("501" in e for e in report["errors"])

    actions = workspace / "backend" / "actions.py"
    src = actions.read_text()
    actions.write_text(src.replace('    raise HTTPException(501, "not implemented")  # AGENT: replace with real logic', BALANCES_IMPL))
    report = verify_workspace_report(workspace)
    assert report["tests"]["passed"] == 3 and report["tests"]["failed"] == 0


def test_locked_files_restored(workspace: Path):
    snap = snapshot_locked(workspace)
    (workspace / "backend" / "tests" / "test_acceptance.py").write_text("def test_ok(): pass\n")
    assert tampered_files(workspace) == ["backend/tests/test_acceptance.py"]
    assert restore_locked(workspace, snap) == ["backend/tests/test_acceptance.py"]
    assert tampered_files(workspace) == []
