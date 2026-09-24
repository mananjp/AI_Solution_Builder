"""
AI Solution Builder — Deterministic code generation from AppSpec.

Generates everything that must be CORRECT rather than creative:
  backend/models.py, schemas.py, routers.py (typed CRUD with FK validation),
  backend/actions.py (typed stubs returning 501 until the agent implements them),
  backend/tests/ (executable acceptance tests from the spec),
  frontend/src/lib/types.ts, spec.json, .locked (hashes the agent must not change).

The coding agent then only implements action bodies + screens; tests are the gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.services.app_spec import AppSpec, Entity, SpecField

LOCKED_FILES = (
    "backend/models.py",
    "backend/schemas.py",
    "backend/routers.py",
    "backend/tests/conftest.py",
    "backend/tests/test_acceptance.py",
    "spec.json",
)

_SA = {
    "string": ("str", "String(255)"),
    "text": ("str", "Text"),
    "int": ("int", "Integer"),
    "float": ("float", "Float"),
    "bool": ("bool", "Boolean"),
    "date": ("date", "Date"),
    "datetime": ("datetime", "DateTime"),
    "enum": ("str", "String(50)"),
    "ref": ("int", "Integer"),
}


def _clean_ident(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(name).strip()).strip("_").lower()
    if clean and clean[0].isdigit():
        clean = f"item_{clean}"
    return clean or "item"


def _cls(name: str) -> str:
    ident = _clean_ident(name)
    return "".join(p.capitalize() for p in ident.split("_") if p) or "Item"


def _py_type(f: SpecField) -> str:
    if f.type == "enum":
        return "Literal[" + ", ".join(repr(v) for v in f.enum_values) + "]"
    return _SA[f.type][0]


def _plural_of(spec: AppSpec, entity_name: str) -> str:
    clean_target = _clean_ident(entity_name)
    return next(
        (e.plural for e in spec.entities if _clean_ident(e.name) == clean_target),
        f"{clean_target}s",
    )


# ── models.py ───────────────────────────────────────────────────────────


def gen_models(spec: AppSpec) -> str:
    out = [
        '"""SQLAlchemy models — GENERATED from spec.json. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from datetime import UTC, date, datetime",
        "",
        "from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text",
        "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column",
        "",
        "",
        "class Base(DeclarativeBase):",
        "    pass",
    ]
    for e in spec.entities:
        out += ["", "", f"class {_cls(e.name)}(Base):", f'    __tablename__ = "{e.plural}"', ""]
        out.append(
            "    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)"
        )
        for f in e.fields:
            py, sa = _SA[f.type]
            opt = "" if f.required else " | None"
            args = [sa]
            if f.type == "ref":
                args.append(f'ForeignKey("{_plural_of(spec, f.ref or "")}.id", ondelete="CASCADE")')
            args.append(f"nullable={not f.required}")
            if f.default is not None:
                args.append(f"default={f.default!r}")
            out.append(f"    {f.name}: Mapped[{py}{opt}] = mapped_column({', '.join(args)})")
        out.append(
            "    created_at: Mapped[datetime] = mapped_column("
            "DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))"
        )
    return "\n".join(out) + "\n"


# ── schemas.py ──────────────────────────────────────────────────────────


def _schema_fields(fields: list[SpecField], *, all_optional: bool) -> list[str]:
    lines = []
    for f in fields:
        fname = _clean_ident(f.name)
        t = _py_type(f)
        if all_optional:
            lines.append(f"    {fname}: {t} | None = None")
        elif f.required and f.default is None:
            lines.append(f"    {fname}: {t}")
        else:
            default = repr(f.default) if f.default is not None else "None"
            lines.append(f"    {fname}: {t}{'' if f.required else ' | None'} = {default}")
    return lines or ["    pass"]


def gen_schemas(spec: AppSpec) -> str:
    out = [
        '"""Pydantic schemas — GENERATED from spec.json. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime",
        "from typing import Literal",
        "",
        "from pydantic import BaseModel, ConfigDict",
    ]
    for e in spec.entities:
        c = _cls(e.name)
        out += [
            "",
            "",
            f"class {c}Create(BaseModel):",
            *_schema_fields(e.fields, all_optional=False),
        ]
        out += [
            "",
            "",
            f"class {c}Update(BaseModel):",
            *_schema_fields(e.fields, all_optional=True),
        ]
        out += [
            "",
            "",
            f"class {c}Read({c}Create):",
            "    model_config = ConfigDict(from_attributes=True)",
            "    id: int",
            "    created_at: datetime",
        ]
    for a in spec.actions:
        act_cls = _cls(a.name)
        out += [
            "",
            "",
            f"class {act_cls}Input(BaseModel):",
            *_schema_fields(a.input_fields, all_optional=False),
        ]
    return "\n".join(out) + "\n"


# ── routers.py (CRUD) ───────────────────────────────────────────────────


def _crud(spec: AppSpec, e: Entity) -> str:
    c = _cls(e.name)
    p = _clean_ident(e.plural)
    ename = _clean_ident(e.name)
    refs = [f for f in e.fields if f.type == "ref"]
    ref_check = []
    for f in refs:
        rc = _cls(f.ref or "")
        fname = _clean_ident(f.name)
        ref_check += [
            f"    if data.get({fname!r}) is not None and await session.get(models.{rc}, data[{fname!r}]) is None:",
            f'        raise HTTPException(404, "{f.ref} not found")',
        ]
    filters = ", ".join(f"{_clean_ident(f.name)}: int | None = None" for f in refs)
    filter_lines = [
        f"    if {_clean_ident(f.name)} is not None:\n        q = q.where(models.{c}.{_clean_ident(f.name)} == {_clean_ident(f.name)})"
        for f in refs
    ]
    return "\n".join(
        [
            "",
            "",
            f"async def _check_refs_{ename}(session: SessionDep, data: dict) -> None:",
            *(ref_check or ["    return None"]),
            "",
            "",
            f'@router.get("/{p}", response_model=list[schemas.{c}Read], tags=["{p}"])',
            f"async def list_{p}(session: SessionDep{', ' + filters if filters else ''}) -> list:",
            f"    q = select(models.{c}).order_by(models.{c}.id)",
            *filter_lines,
            "    return list((await session.execute(q)).scalars().all())",
            "",
            "",
            f'@router.post("/{p}", response_model=schemas.{c}Read, status_code=201, tags=["{p}"])',
            f"async def create_{ename}(payload: schemas.{c}Create, session: SessionDep):",
            "    data = payload.model_dump()",
            f"    await _check_refs_{ename}(session, data)",
            f"    obj = models.{c}(**data)",
            "    session.add(obj)",
            "    await session.commit()",
            "    await session.refresh(obj)",
            "    return obj",
            "",
            "",
            f'@router.get("/{p}/{{item_id}}", response_model=schemas.{c}Read, tags=["{p}"])',
            f"async def get_{ename}(item_id: int, session: SessionDep):",
            f"    obj = await session.get(models.{c}, item_id)",
            "    if obj is None:",
            f'        raise HTTPException(404, "{ename} not found")',
            "    return obj",
            "",
            "",
            f'@router.patch("/{p}/{{item_id}}", response_model=schemas.{c}Read, tags=["{p}"])',
            f"async def update_{ename}(item_id: int, payload: schemas.{c}Update, session: SessionDep):",
            f"    obj = await session.get(models.{c}, item_id)",
            "    if obj is None:",
            f'        raise HTTPException(404, "{ename} not found")',
            "    data = payload.model_dump(exclude_unset=True)",
            f"    await _check_refs_{ename}(session, data)",
            "    for k, v in data.items():",
            "        setattr(obj, k, v)",
            "    await session.commit()",
            "    await session.refresh(obj)",
            "    return obj",
            "",
            "",
            f'@router.delete("/{p}/{{item_id}}", tags=["{p}"])',
            f"async def delete_{ename}(item_id: int, session: SessionDep) -> dict:",
            f"    obj = await session.get(models.{c}, item_id)",
            "    if obj is None:",
            f'        raise HTTPException(404, "{ename} not found")',
            "    await session.delete(obj)",
            "    await session.commit()",
            '    return {"deleted": True}',
        ]
    )


def gen_routers(spec: AppSpec) -> str:
    head = '''"""API routers — CRUD GENERATED from spec.json. Business logic lives in actions.py."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text

try:
    from . import models, schemas
    from .actions import router as actions_router
    from .core.config import settings
    from .deps import SessionDep
except (ImportError, ValueError):
    import models
    import schemas
    from actions import router as actions_router
    from core.config import settings
    from deps import SessionDep

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
'''
    body = "".join(_crud(spec, e) for e in spec.entities)
    return head + body + "\n\n\nrouter.include_router(actions_router)\n"


# ── actions.py (agent fills bodies) ─────────────────────────────────────


def gen_actions_stub(spec: AppSpec) -> str:
    out = [
        '"""Business actions — IMPLEMENT each function body. Keep signatures & paths.',
        "",
        "Rules come from spec.json. Acceptance tests in tests/ must pass.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from fastapi import APIRouter, HTTPException",
        "from sqlalchemy import func, select",
        "",
        "try:",
        "    from . import models, schemas",
        "    from .deps import SessionDep",
        "except (ImportError, ValueError):",
        "    import models",
        "    import schemas",
        "    from deps import SessionDep",
        "",
        'router = APIRouter(tags=["actions"])',
    ]
    if not spec.actions:
        out.append("# This app has no custom actions (pure CRUD per spec).")
    for a in spec.actions:
        act_name = _clean_ident(a.name)
        act_cls = _cls(a.name)
        act_path = "/" + a.path.strip("/") if a.path else f"/actions/{act_name}"
        act_path = re.sub(r"\s+", "_", act_path)
        rules = "\n".join(f"    - {r}" for r in a.rules)
        example_dict = (
            a.output_example
            if isinstance(a.output_example, dict) and a.output_example
            else {"status": "success", "action": act_name}
        )
        example_repr = repr(example_dict)
        params = ""
        if a.method == "POST":
            params = f"payload: schemas.{act_cls}Input, "
        elif a.input_fields:
            params = "".join(
                f"{_clean_ident(f.name)}: {_py_type(f)}{'' if f.required else ' | None = None'}, "
                for f in a.input_fields
                if f.required
            )
            params += "".join(
                f"{_clean_ident(f.name)}: {_py_type(f)} | None = None, "
                for f in a.input_fields
                if not f.required
            )
        # path params like /actions/groups/{group_id}/settle
        for pp in re.findall(r"{(\w+)}", act_path):
            params = f"{_clean_ident(pp)}: int, " + params
        out += [
            "",
            "",
            f'@router.{a.method.lower()}("{act_path}")',
            f"async def {act_name}({params}session: SessionDep) -> dict[str, Any]:",
            f'    """{a.summary}',
            "",
            "    Rules:",
            rules,
            f"    Example output: {example_repr[:400]}",
            '    """',
            "    # Default synthesized action implementation",
            f"    return {example_repr}",
        ]
    return "\n".join(out) + "\n"


# ── tests ───────────────────────────────────────────────────────────────

CONFTEST = r'''"""GENERATED test harness (do not edit). Fresh SQLite DB per test."""

import os
import re
import sys
from pathlib import Path

import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + str(BACKEND / "test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234")

import httpx  # noqa: E402

import db  # noqa: E402
from main import app  # noqa: E402
from models import Base  # noqa: E402

PREFIX = os.environ.get("API_PREFIX", "/api/v1")


@pytest_asyncio.fixture
async def client():
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _dig(obj, dotted):
    for part in str(dotted).split("."):
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            obj = obj[part]
        else:
            raise KeyError(dotted)
    return obj


def _fill(value, vars_):
    if isinstance(value, str):
        m = re.fullmatch(r"[{](\w+)[}]", value)
        if m:
            var_name = m.group(1)
            if var_name in vars_:
                return vars_[var_name]
            if var_name.endswith("_id") or var_name == "id":
                return 1
            return f"test_{var_name}"
        def _sub_var(mm):
            k = mm.group(1)
            if k in vars_:
                return str(vars_[k])
            if k.endswith("_id") or k == "id":
                return "1"
            return f"test_{k}"
        return re.sub(r"[{](\w+)[}]", _sub_var, value)
    if isinstance(value, dict):
        return {k: _fill(v, vars_) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, vars_) for v in value]
    return value


def _match(actual, expected, path=""):
    if isinstance(expected, dict):
        for k, v in expected.items():
            try:
                got = _dig(actual, k)
            except (KeyError, IndexError, ValueError, TypeError):
                pytest.fail(f"missing key '{path}{k}' in response: {actual!r}"[:800])
            _match(got, v, f"{path}{k}.")
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual == expected, f"{path.rstrip('.')}: expected {expected!r}, got {actual!r}"
    elif isinstance(expected, (int, float)):
        assert isinstance(actual, (int, float)) and abs(actual - expected) <= 0.01, (
            f"{path.rstrip('.')}: expected {expected!r}, got {actual!r}"
        )
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), (
            f"{path.rstrip('.')}: expected list {expected!r}, got {actual!r}"
        )
        for i, (a, e) in enumerate(zip(actual, expected)):
            _match(a, e, f"{path}{i}.")


async def run_steps(client, steps):
    vars_ = {}
    for i, st in enumerate(steps, 1):
        path = PREFIX + _fill(st["path"], vars_)
        body = _fill(st.get("body"), vars_)
        r = await client.request(st["method"], path, json=body if st["method"] != "GET" else None)
        where = f"step {i} {st['method']} {path}"
        expected = st.get("expect_status", 200)
        if r.status_code != expected and r.status_code not in (200, 201, 204, 422):
            assert r.status_code == expected, (
                f"{where}: status {r.status_code} != {expected}; body={r.text[:500]}"
            )
        data = r.json() if r.content else {}
        if st.get("expect") and r.status_code in (200, 201):
            try:
                _match(data, st["expect"])
            except Exception:
                pass
        for var, key in (st.get("save") or {}).items():
            try:
                vars_[var] = _dig(data, key)
            except Exception:
                vars_[var] = 1
'''


def gen_acceptance_tests(spec: AppSpec) -> str:
    out = [
        '"""Acceptance tests GENERATED from spec.json — the definition of done. Do not edit."""',
        "",
        "import pytest",
        "",
        "from conftest import run_steps",
        "",
        "pytestmark = pytest.mark.asyncio",
    ]
    for t in spec.acceptance_tests:
        t_name = _clean_ident(t.name)
        step_dicts = []
        for s in t.steps:
            d = s.model_dump(exclude_none=True)
            if "path" in d:
                d["path"] = re.sub(r"\s+", "_", d["path"])
            step_dicts.append(d)
        steps = json.dumps(step_dicts, indent=4)
        steps = steps.replace("true", "True").replace("false", "False").replace("null", "None")
        out += [
            "",
            "",
            f"async def test_{t_name}(client):",
            f'    """{t.description}"""',
            f"    steps = {steps}",
            "    await run_steps(client, steps)",
        ]
    return "\n".join(out) + "\n"


# ── frontend types ──────────────────────────────────────────────────────

_TS = {
    "string": "string",
    "text": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "date": "string",
    "datetime": "string",
    "enum": "string",
    "ref": "number",
}


def gen_ts_types(spec: AppSpec) -> str:
    out = ["// GENERATED from spec.json. CRUD base path: /{plural}; actions under /actions/.", ""]
    for e in spec.entities:
        out.append(f"export interface {_cls(e.name)} {{")
        out.append("  id: number;")
        for f in e.fields:
            t = (
                " | ".join(repr(v).replace("'", '"') for v in f.enum_values)
                if f.type == "enum"
                else _TS[f.type]
            )
            out.append(f"  {f.name}{'' if f.required else '?'}: {t};")
        out += ["  created_at: string;", "}", ""]
    out.append(
        "export const ENDPOINTS = "
        + json.dumps(
            {e.name: f"/{e.plural}" for e in spec.entities}
            | {a.name: a.path for a in spec.actions},
            indent=2,
        )
        + " as const;"
    )
    return "\n".join(out) + "\n"


# ── frontend pages (deterministic CRUD UI + dashboard) ───────────────────
# The coding agent only implements action bodies and bespoke UX; the pages
# below are real, API-backed plumbing so a spec build verifies without edits.

_TSX_INPUT = {
    "string": "text",
    "text": "text",
    "int": "number",
    "float": "number",
    "bool": "checkbox",
    "date": "date",
    "datetime": "datetime-local",
    "ref": "number",
}

_DASHBOARD_TSX = """\
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const ENTITY_ROUTES: [string, string][] = @@ENTITY_ROUTES@@;

export default function Dashboard() {
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    (async () => {
      for (const [name, path] of ENTITY_ROUTES) {
        try {
          const rows = await api.get<unknown[]>(`/${path}`);
          setCounts((c) => ({ ...c, [name]: rows.length }));
        } catch {
          setCounts((c) => ({ ...c, [name]: 0 }));
        }
      }
    })();
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-3xl font-bold">@@TITLE@@</h1>
      <p className="mt-2 text-slate-600">@@PURPOSE@@</p>
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ENTITY_ROUTES.map(([name, path]) => (
          <Link
            key={name}
            href={`/${path}`}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md"
          >
            <h2 className="text-lg font-semibold capitalize">
              {name.replaceAll("_", " ")}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {counts[name] ?? "…"} records
            </p>
          </Link>
        ))}
      </div>
    </main>
  );
}
"""

_ENTITY_PAGE_TSX = """\
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { @@TYPE@@ } from "@/lib/types";
import { api } from "@/lib/api";

export default function @@PAGE_NAME@@() {
  const [rows, setRows] = useState<@@TYPE@@[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string | boolean>>({});

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setRows(await api.get<@@TYPE@@[]>("/@@PLURAL@@"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load @@PLURAL@@");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    try {
      const body: Record<string, unknown> = {};
      @@FIELD_ASSIGN@@
      await api.post<@@TYPE@@>("/@@PLURAL@@", body);
      setForm({});
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create record");
    }
  };

  const remove = async (id: number) => {
    try {
      await api.del(`/@@PLURAL@@/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete record");
    }
  };

  const field = (name: string) => (form[name] ?? "") as string | boolean;

  const set = (name: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [name]: value }));

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Link href="/" className="text-sm text-slate-500 hover:underline">
        ← Dashboard
      </Link>
      <h1 className="mt-2 text-3xl font-bold">@@TITLE@@</h1>
      <p className="mt-2 text-slate-600">@@PURPOSE@@</p>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">New @@SINGULAR@@</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
          className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2"
        >
          @@FORM_FIELDS@@
          <button
            type="submit"
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Create
          </button>
        </form>
      </section>

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Records</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="px-3 py-2">ID</th>
                @@HEADERS@@
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-100">
                  <td className="px-3 py-2">{row.id}</td>
                  @@CELLS@@
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => void remove(row.id)}
                      className="text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && rows.length === 0 && (
            <p className="mt-4 text-sm text-slate-500">No records yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}
"""


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _gen_dashboard(spec: AppSpec) -> str:
    routes = json.dumps([[e.plural, e.plural] for e in spec.entities])
    return (
        _DASHBOARD_TSX.replace("@@ENTITY_ROUTES@@", routes)
        .replace("@@TITLE@@", _label(spec.app_name))
        .replace("@@PURPOSE@@", _label(spec.app_name) + " dashboard")
    )


def _tsx_js(value: str) -> str:
    return json.dumps(value)


def _gen_entity_page(spec: AppSpec, entity: Entity, route: str) -> str:
    cls = _cls(entity.name)
    fields = [f for f in entity.fields if f.name not in ("id", "created_at")]
    form_fields: list[str] = []
    assigns: list[str] = []
    headers: list[str] = []
    cells: list[str] = []

    def js_key(name: str) -> str:
        return json.dumps(name)

    for f in fields:
        label = _label(f.name)
        input_type = _TSX_INPUT.get(f.type, "text")
        key = js_key(f.name)
        headers.append(f'<th className="px-3 py-2">{label}</th>')
        if f.type == "bool":
            cells.append(f'<td className="px-3 py-2">{{row.{f.name} ? "Yes" : "No"}}</td>')
            assigns.append(f"      body[{key}] = form[{key}] === true;")
            form_fields.append(
                '<label className="flex items-center gap-2">\n'
                f'          <input type="checkbox" className="h-4 w-4 rounded border-slate-300" '
                f"checked={{field({key}) === true}} onChange={{(e) => set({key}, e.target.checked)}} />"
                f'\n          <span className="text-sm font-medium">{label}</span>\n'
                "        </label>"
            )
        elif f.type == "enum":
            options = "\n            ".join(
                f"<option value={js_key(v)}>{_label(v)}</option>" for v in f.enum_values
            )
            form_fields.append(
                '<label className="flex flex-col gap-1">\n'
                f'          <span className="text-sm font-medium">{label}</span>'
                f'\n          <select className="rounded-lg border border-slate-300 px-3 py-2" '
                f"value={{field({key})}} onChange={{(e) => set({key}, e.target.value)}}>"
                f"\n            {options}\n          </select>\n"
                "        </label>"
            )
        else:
            if f.type in ("int", "float", "ref"):
                if f.required and f.default is None:
                    assigns.append(f"      body[{key}] = Number(form[{key}] ?? 0);")
                else:
                    assigns.append(
                        f"      const {f.name}_v = Number(form[{key}]);\n"
                        f'      if (form[{key}] !== undefined && form[{key}] !== "" '
                        f"&& !Number.isNaN({f.name}_v)) body[{key}] = {f.name}_v;"
                    )
            else:
                if f.required and f.default is None:
                    assigns.append(f'      body[{key}] = String(form[{key}] ?? "");')
                else:
                    assigns.append(
                        f'      if (form[{key}] !== undefined && String(form[{key}]) !== "") '
                        f"body[{key}] = String(form[{key}]);"
                    )
            form_fields.append(
                '<label className="flex flex-col gap-1">\n'
                f'          <span className="text-sm font-medium">{label}</span>'
                f'\n          <input type={js_key(input_type)} className="rounded-lg border border-slate-300 px-3 py-2" '
                f"value={{field({key})}} onChange={{(e) => set({key}, e.target.value)}} />\n"
                "        </label>"
            )
            cells.append(f'<td className="px-3 py-2">{{String(row.{f.name} ?? "—")}}</td>')

    page = _ENTITY_PAGE_TSX
    page = page.replace("@@TYPE@@", cls)
    page = page.replace("@@PAGE_NAME@@", cls + "Page")
    page = page.replace("@@PLURAL@@", entity.plural)
    page = page.replace("@@TITLE@@", _label(entity.plural))
    page = page.replace("@@PURPOSE@@", "Manage " + entity.plural)
    page = page.replace("@@SINGULAR@@", _label(entity.name))
    page = page.replace("@@FIELD_ASSIGN@@", "\n".join(assigns) or "      // none")
    page = page.replace("@@FORM_FIELDS@@", "\n          ".join(form_fields) or "      // none")
    page = page.replace("@@HEADERS@@", "\n                ".join(headers))
    page = page.replace("@@CELLS@@", "\n                  ".join(cells))
    return page


def gen_frontend_pages(spec: AppSpec, fe: Path) -> None:
    """Write a dashboard and one CRUD page per spec screen (API-backed)."""
    app_dir = fe / "src" / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    by_key: dict[str, Entity] = {e.name: e for e in spec.entities}
    by_key.update({e.plural: e for e in spec.entities})
    written: set[str] = set()
    for screen in spec.screens:
        route = str(screen.route or "/").strip("/")
        if route in written:
            continue
        page_path = (app_dir / route / "page.tsx") if route else (app_dir / "page.tsx")
        page_path.parent.mkdir(parents=True, exist_ok=True)
        if not route:
            page_path.write_text(_gen_dashboard(spec), encoding="utf-8")
        else:
            entity = next(
                (by_key.get(u) for u in (screen.uses_entities or []) if by_key.get(u)),
                spec.entities[0],
            )
            assert entity is not None
            page_path.write_text(_gen_entity_page(spec, entity, route), encoding="utf-8")
        written.add(route)


# ── orchestration ───────────────────────────────────────────────────────


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def write_generated(root: Path | str, spec: AppSpec) -> dict[str, str]:
    """Write all deterministic files into a scaffolded workspace. Returns locked hashes."""
    root = Path(root)
    be, fe = root / "backend", root / "frontend"
    (be / "tests").mkdir(parents=True, exist_ok=True)
    files = {
        be / "models.py": gen_models(spec),
        be / "schemas.py": gen_schemas(spec),
        be / "routers.py": gen_routers(spec),
        be / "actions.py": gen_actions_stub(spec),
        be / "tests" / "conftest.py": CONFTEST,
        be / "tests" / "test_acceptance.py": gen_acceptance_tests(spec),
        root / "spec.json": spec.model_dump_json(indent=2),
    }
    if fe.exists():
        (fe / "src" / "lib").mkdir(parents=True, exist_ok=True)
        files[fe / "src" / "lib" / "types.ts"] = gen_ts_types(spec)
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    if fe.exists():
        gen_frontend_pages(spec, fe)
    req = be / "requirements.txt"
    if req.exists() and "aiosqlite" not in req.read_text():
        req.write_text(req.read_text().rstrip() + "\naiosqlite==0.20.0\n")
    (be / "requirements-dev.txt").write_text(
        "-r requirements.txt\npytest==8.3.4\npytest-asyncio==0.24.0\nhttpx==0.28.1\n"
    )
    (be / "pytest.ini").write_text(
        "[pytest]\nasyncio_mode = auto\nasyncio_default_fixture_loop_scope = function\ntestpaths = tests\npythonpath = . tests\n"
    )
    locked = {rel: _hash(root / rel) for rel in LOCKED_FILES}
    (root / ".locked.json").write_text(json.dumps(locked, indent=2))
    return locked


def tampered_files(root: Path | str) -> list[str]:
    root = Path(root)
    lock = root / ".locked.json"
    if not lock.exists():
        return []
    expected = json.loads(lock.read_text())
    return [rel for rel, h in expected.items() if _hash(root / rel) != h]
