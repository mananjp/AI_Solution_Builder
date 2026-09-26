"""Compile-check every preset template end to end.

For each of the four presets this:
  1. derives its AppSpec (fallback path, no LLM) from the template's own
     er_diagram, exactly as an offline build would,
  2. generates the FastAPI backend + Next.js frontend into a copy of the
     scaffold that has the shadcn components installed,
  3. runs `python -m compileall` on the generated backend, and
  4. runs `tsc --noEmit` on the generated frontend.

Exit code is non-zero if any template fails either compiler.
"""

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"
SCAFFOLD = BACKEND / "opencode" / "templates" / "mvp" / "frontend"
WORKROOT = Path(r"C:\Users\Ansh\AppData\Local\Temp\opencode\gen_checks")
NODE_MODULES = Path(r"C:\Users\Ansh\AppData\Local\Temp\opencode\scaffold_build\node_modules")
PY = Path(r"C:\Users\Ansh\AppData\Local\Temp\opencode\venv312\Scripts\python.exe")

sys.path.insert(0, str(BACKEND))

from app.services import spec_codegen, templates  # noqa: E402
from app.services.app_spec import AppSpec, fallback_app_spec  # noqa: E402


def spec_for(slug: str, ai_state: dict) -> AppSpec:
    """Build a validated AppSpec from a preset's derived ER diagram."""
    entities = []
    for ent in ai_state["er_diagram"]["content"]["entities"]:
        fields = []
        for f in ent["fields"]:
            ftype = str(f.get("type", "string")).lower()
            mapping = {
                "uuid": "string",
                "varchar(255)": "string",
                "varchar(100)": "string",
                "varchar(50)": "string",
                "text": "text",
                "timestamptz": "datetime",
                "float": "float",
                "boolean": "bool",
                "integer": "int",
            }
            spec_type = mapping.get(ftype, "string")
            fields.append(
                {
                    "name": f["name"],
                    "type": spec_type,
                    "required": not f.get("pk"),
                    **({"default": f["default"]} if "default" in f else {}),
                    **({"enum_values": ["a", "b"]} if spec_type == "enum" else {}),
                }
            )
        entities.append({"name": ent["name"], "plural": _plural(ent["name"]), "fields": fields})

    state = {
        "solution_title": ai_state["solution_title"],
        "business_description": ai_state["business_description"],
        "hld": ai_state["hld"],
        "lld": ai_state["lld"],
        "er_diagram": ai_state["er_diagram"],
    }
    return fallback_app_spec(state)


def _plural(name: str) -> str:
    from app.services.app_spec import pluralize

    return pluralize(name)


ALL_TYPES_SPEC = {
    "app_name": "Field Type Matrix",
    "one_liner": "Exercise every supported field type.",
    "core_value": "Verify every field type renders and compiles.",
    "entities": [
        {
            "name": "record",
            "plural": "records",
            "fields": [
                {"name": "id", "type": "string", "required": True},
                {"name": "title", "type": "string", "required": True},
                {"name": "notes", "type": "text", "required": False},
                {"name": "quantity", "type": "int", "required": True},
                {"name": "price", "type": "float", "required": False},
                {"name": "is_active", "type": "bool", "required": False, "default": True},
                {"name": "due_date", "type": "date", "required": False},
                {"name": "due_at", "type": "datetime", "required": False},
                {
                    "name": "status",
                    "type": "enum",
                    "required": False,
                    "enum_values": ["draft", "active", "archived"],
                },
                {"name": "owner_id", "type": "ref", "required": False, "ref": "record"},
            ],
        }
    ],
    "actions": [],
    "screens": [
        {
            "name": "Dashboard",
            "route": "",
            "purpose": "Overview",
            "uses_entities": ["record"],
            "uses_actions": [],
            "key_interactions": ["view records"],
        },
        {
            "name": "Records",
            "route": "records",
            "purpose": "Manage records",
            "uses_entities": ["record"],
            "uses_actions": [],
            "key_interactions": ["list", "create"],
        },
    ],
    "acceptance_tests": [
        {
            "name": "lists records",
            "description": "Records are listed on dashboard",
            "steps": [
                {"method": "GET", "path": "/records", "expect_status": 200}
            ],
        },
        {
            "name": "creates a record",
            "description": "New record can be created",
            "steps": [
                {"method": "POST", "path": "/records", "body": {"title": "x"}, "expect_status": 201}
            ],
        },
        {
            "name": "validates input",
            "description": "Invalid input rejected",
            "steps": [
                {"method": "POST", "path": "/records", "body": {}, "expect_status": 422}
            ],
        },
    ],
}


def check_all_types() -> list[str]:
    """Exercise every field-type branch of the entity page generator."""
    print(f"\n{'=' * 62}\n== synthetic: all field types\n{'=' * 62}")
    problems: list[str] = []
    work = WORKROOT / "__all_types"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fe = work / "frontend"
    shutil.copytree(SCAFFOLD, fe, ignore=shutil.ignore_patterns("node_modules"))
    if NODE_MODULES.exists():
        try:
            (fe / "node_modules").symlink_to(NODE_MODULES, target_is_directory=True)
        except OSError:
            shutil.copytree(NODE_MODULES, fe / "node_modules", symlinks=True)

    spec = AppSpec.model_validate(ALL_TYPES_SPEC)
    spec_codegen.write_generated(work, spec)

    rc, out = run(f'"{PY}" -m compileall -q app', work / "backend")
    print("  backend compileall:", "ok" if rc == 0 else "FAIL")
    if rc != 0:
        problems.append(f"all_types: backend compileall\n{out[-1500:]}")

    rc, out = run("npx tsc --noEmit", fe)
    print("  frontend tsc:", "ok" if rc == 0 else "FAIL")
    if rc != 0:
        problems.append(f"all_types: frontend tsc\n{out[-3000:]}")

    page = fe / "src" / "app" / "records" / "page.tsx"
    if page.exists():
        body = page.read_text(encoding="utf-8")
        for token in ("<Checkbox", "<Select", "<Input", "<Label", "<TableHead", "<TableCell"):
            if token not in body:
                problems.append(f"all_types: {token} never generated")
        for bad in ("slate-", "Skiper"):
            if bad in body and "muted-foreground" not in body:
                problems.append(f"all_types: raw {bad} leaked into generated page")
    else:
        problems.append("all_types: records page not generated")
    return problems


def run(cmd: str, cwd: Path) -> tuple[int, str]:
    # A single string, because shell=True joins a list on Windows by just
    # concatenating it, producing an unrecognised 'cmd arg' executable name.
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=True)
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    failures: list[str] = []
    WORKROOT.mkdir(parents=True, exist_ok=True)

    for tpl in templates.TEMPLATES:
        slug = tpl.slug
        print(f"\n{'=' * 62}\n== {slug}: {tpl.title}\n{'=' * 62}")
        ai_state = tpl.build_ai_state()

        try:
            spec = spec_for(slug, ai_state)
        except Exception as exc:  # noqa: BLE001
            print(f"  SPEC FAIL: {type(exc).__name__}: {exc}")
            failures.append(f"{slug}: spec {exc}")
            continue

        print(f"  spec ok: {spec.app_name} | {len(spec.entities)} entities, {len(spec.screens)} screens")

        work = WORKROOT / slug
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        # Mirror the real layout write_generated() expects: <root>/frontend
        # and <root>/backend, so generated file placement is faithful.
        fe = work / "frontend"
        shutil.copytree(SCAFFOLD, fe, ignore=shutil.ignore_patterns("node_modules"))
        if NODE_MODULES.exists():
            try:
                (fe / "node_modules").symlink_to(NODE_MODULES, target_is_directory=True)
            except OSError:
                shutil.copytree(NODE_MODULES, fe / "node_modules", symlinks=True)
        be_scaffold = SCAFFOLD.parent / "backend"
        if be_scaffold.exists():
            shutil.copytree(be_scaffold, work / "backend")

        # ── generate backend + frontend together (this is the real path) ──
        try:
            written = spec_codegen.write_generated(work, spec)
            print(f"  generated {len(written)} files")
        except Exception as exc:  # noqa: BLE001
            print(f"  GEN FAIL: {type(exc).__name__}: {exc}")
            failures.append(f"{slug}: write_generated {exc}")
            continue

        if not (fe / "src" / "lib" / "types.ts").exists():
            print("  FAIL: generated src/lib/types.ts is missing")
            failures.append(f"{slug}: missing src/lib/types.ts")

        # ── backend ────────────────────────────────────────────────────────
        rc, out = run(f'"{PY}" -m compileall -q app', work / "backend")
        if rc != 0:
            print(f"  BACKEND COMPILE FAIL:\n{out[-2500:]}")
            failures.append(f"{slug}: backend compileall")
        else:
            print("  backend compileall: ok")

        # ── frontend ───────────────────────────────────────────────────────
        rc, out = run("npx tsc --noEmit", fe)
        if rc != 0:
            print(f"  FRONTEND TSC FAIL:\n{out[-3000:]}")
            failures.append(f"{slug}: frontend tsc")
        else:
            print("  frontend tsc: ok")

    print(f"\n{'=' * 62}")
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"ALL {len(templates.TEMPLATES)} TEMPLATES COMPILE CLEAN")

    # ── synthetic all-types matrix ───────────────────────────────────────
    extra = check_all_types()
    if extra:
        print(f"ALL-TYPES FAILURES ({len(extra)}):")
        for e in extra:
            print(f"  - {e}")
        return 1
    print("ALL-TYPES MATRIX COMPILES CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
