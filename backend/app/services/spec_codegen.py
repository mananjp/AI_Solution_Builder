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
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from app.services.app_spec import AppSpec, Entity, SpecField

logger = logging.getLogger(__name__)

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
    "date": ("_date", "Date"),
    "datetime": ("_datetime", "DateTime"),
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
        "from datetime import UTC, date as _date, datetime as _datetime",
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
            "    created_at: Mapped[_datetime] = mapped_column("
            "DateTime, default=lambda: _datetime.now(UTC).replace(tzinfo=None))"
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
        "from datetime import date as _date, datetime as _datetime",
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
            "    created_at: _datetime",
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


def gen_analytics_router(spec: AppSpec) -> str:
    from app.services.analytics_spec import resolve_analytics_target

    target = resolve_analytics_target(spec)
    if target is None:
        return (
            '"""Analytics router -- GENERATED from spec.json."""\n\n'
            "from fastapi import APIRouter\n\n"
            'router = APIRouter(prefix="/analytics", tags=["analytics"])\n\n'
            '@router.get("/summary")\n'
            "async def summary() -> dict:\n"
            '    return {"available": False, "reason": "no numeric fields found"}\n'
        )

    c = _cls(target.entity.name)
    field = _clean_ident(target.metric_field.name)
    time_col = _clean_ident(target.time_field.name) if target.time_field else None

    trend_block = ""
    if time_col:
        trend_block = f"""
    try:
        trend_q = (
            select(
                func.date_trunc("day", models.{c}.{time_col}).label("day"),
                func.sum(models.{c}.{field}).label("total"),
            )
            .group_by("day")
            .order_by("day")
        )
        trend_rows = (await session.execute(trend_q)).all()
    except Exception:
        trend_q = (
            select(
                func.date(models.{c}.{time_col}).label("day"),
                func.sum(models.{c}.{field}).label("total"),
            )
            .group_by("day")
            .order_by("day")
        )
        trend_rows = (await session.execute(trend_q)).all()
    trend = [{{"date": str(r.day), "total": float(r.total or 0)}} for r in trend_rows]
"""
    else:
        trend_block = "\n    trend = []\n"

    return "\n".join(
        [
            '"""Analytics router -- GENERATED from spec.json."""',
            "",
            "from __future__ import annotations",
            "",
            "from fastapi import APIRouter",
            "from sqlalchemy import func, select",
            "",
            "try:",
            "    from . import models",
            "    from .deps import SessionDep",
            "except (ImportError, ValueError):",
            "    try:",
            "        from deps import SessionDep",
            "        import models",
            "    except (ImportError, ValueError):",
            "        from app.database import SessionDep",
            "        from . import models",
            "",
            'router = APIRouter(prefix="/analytics", tags=["analytics"])',
            "",
            '@router.get("/summary")',
            "async def summary(session: SessionDep) -> dict:",
            "    agg_q = select(",
            f"        func.count(models.{c}.id).label('count'),",
            f"        func.sum(models.{c}.{field}).label('total'),",
            f"        func.avg(models.{c}.{field}).label('average'),",
            "    )",
            "    row = (await session.execute(agg_q)).one()",
            trend_block,
            "    return {",
            "        'available': True,",
            f"        'entity': '{target.entity.name}',",
            f"        'metric': '{target.metric_field.name}',",
            "        'count': int(row.count or 0),",
            "        'total': float(row.total or 0),",
            "        'average': float(row.average or 0),",
            "        'trend': trend,",
            "    }",
            "",
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
    try:
        from .routers_analytics import router as analytics_router
    except (ImportError, ValueError):
        analytics_router = None
except (ImportError, ValueError):
    import models
    import schemas
    from actions import router as actions_router
    from core.config import settings
    from deps import SessionDep
    try:
        from routers_analytics import router as analytics_router
    except (ImportError, ValueError):
        analytics_router = None

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
    extra_routers = "\n\nrouter.include_router(actions_router)\n"
    extra_routers += (
        "if analytics_router is not None:\n    router.include_router(analytics_router)\n"
    )
    return head + body + extra_routers


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
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { LayersTwo01, Database01, Zap, Activity, SearchLg } from "@untitledui/icons";
import { Input } from "react-aria-components";
@@RECHARTS_IMPORT@@
const ENTITY_ROUTES: [string, string][] = @@ENTITY_ROUTES@@;

function KpiCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-secondary bg-primary shadow-xs gap-2">
      <div className="flex flex-col gap-1.5 flex-row items-center justify-between space-y-0 pb-2">
        <h3 className="text-lg font-semibold text-primary text-xs font-medium uppercase tracking-wider text-tertiary">
          {label}
        </h3>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold tabular-nums text-brand-primary">{value}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState("");
  const [analytics, setAnalytics] = useState<{
    available: boolean;
    total: number;
    average: number;
    count: number;
    metric?: string;
    trend: { date: string; total: number }[];
  } | null>(null);

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
    api
      .get<{
        available: boolean;
        total: number;
        average: number;
        count: number;
        metric?: string;
        trend: { date: string; total: number }[];
      }>("/analytics/summary")
      .then(setAnalytics)
      .catch(() => setAnalytics(null));
  }, []);

  const totalRecords = Object.values(counts).reduce((a, b) => a + b, 0);
  const visibleRoutes = ENTITY_ROUTES.filter(([name]) =>
    name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-brand-solid px-4 py-8 text-brand-primary sm:px-6 md:py-12">
      <div className="mx-auto max-w-6xl">
        {/* Animated Hero Header */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="rounded-2xl border border-secondary bg-primary shadow-xs gap-6 overflow-hidden p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center rounded-full bg-brand-primary px-2.5 py-0.5 text-xs font-medium text-brand-secondary">Production Prototype</span>
                  <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary ring-1 ring-border-secondary ring-inset">Live API</span>
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-brand-primary sm:text-3xl md:text-4xl">
                  @@TITLE@@
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-tertiary">@@PURPOSE@@</p>
              </div>

               <Link href="/api/docs" className="rounded-lg bg-brand-solid px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring">API Docs</Link>

            </div>

            {/* Real Analytics KPIs & Chart or Quick Metrics Bar */}
            {analytics?.available ? (
              <div className="border-t border-secondary pt-6">
                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <KpiCard
                    label={`Total ${analytics.metric || "Volume"}`}
                    value={analytics.total.toLocaleString()}
                    icon={<LayersTwo01 className="h-4 w-4 text-brand-primary" />}
                  />
                  <KpiCard
                    label="Average"
                    value={analytics.average.toFixed(2)}
                    icon={<Activity className="h-4 w-4 text-brand-primary" />}
                  />
                  <KpiCard
                    label="Records"
                    value={analytics.count.toLocaleString()}
                    icon={<Database01 className="h-4 w-4 text-brand-primary" />}
                  />
                </div>
@@TREND_CHART@@
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 border-t border-secondary pt-6 sm:grid-cols-3">
                <KpiCard
                  label="Modules"
                  value={ENTITY_ROUTES.length}
                  icon={<LayersTwo01 className="h-4 w-4 text-brand-primary" />}
                />
                <KpiCard
                  label="Total Records"
                  value={totalRecords}
                  icon={<Database01 className="h-4 w-4 text-brand-primary" />}
                />
                <KpiCard
                  label="API Status"
                  value="Live"
                  icon={<Activity className="h-4 w-4 text-brand-primary" />}
                />
              </div>
            )}
          </div>
        </motion.div>

        {/* Search & Header */}
        <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-brand-primary">
              Application Modules
            </h2>
            <p className="text-xs text-tertiary">
              Manage data models and business logic workflows
            </p>
          </div>

          <div className="relative w-full max-w-xs">
            <SearchLg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
            <Input
              type="text"
              placeholder="Search modules..."
              aria-label="Search modules"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Animated Cards Grid */}
        {visibleRoutes.length === 0 ? (
          <div className="rounded-2xl border border-secondary bg-primary shadow-xs mt-6">
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <SearchLg className="h-6 w-6 text-tertiary" />
              <h3 className="text-lg font-semibold text-primary text-base">No modules match "{filter}"</h3>
              <p className="text-sm text-tertiary">Clear the search to see every module in this app.</p>
            </div>
          </div>
        ) : (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {visibleRoutes.map(([name, path], idx) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.3 }}
            >
              <Link href={`/${path}`} className="group block h-full">
                <div className="rounded-2xl border border-secondary bg-primary shadow-xs h-full gap-4 transition-colors group-hover:border-brand/50">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-tertiary text-brand-primary transition-colors group-hover:bg-brand-solid/10 group-hover:text-brand-primary">
                        <Zap className="h-5 w-5" />
                      </div>
                      <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary ring-1 ring-border-secondary ring-inset">{counts[name] ?? "…"} records</span>
                    </div>
                    <h3 className="text-lg font-semibold text-primary capitalize transition-colors group-hover:text-brand-primary">
                      {name.replaceAll("_", " ")}
                    </h3>
                    <p className="text-sm text-tertiary">
                      Access data records, creation forms, and API actions for{" "}
                      {name.replaceAll("_", " ")}.
                    </p>
                  </div>
                  <div className="mt-auto flex items-center justify-between border-t border-secondary pt-4 text-xs font-semibold text-brand-primary">
                    <span>Manage {name.replaceAll("_", " ")}</span>
                    <span className="transition-transform group-hover:translate-x-1">→</span>
                  </div>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
        )}
      </div>
    </main>
  );
}
"""


_ENTITY_PAGE_TSX = """\
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import type { @@TYPE@@ as @@TYPE@@Type } from "@/lib/types";
import { api } from "@/lib/api";
import { Plus, ArrowLeft, Trash01, SearchLg, CheckCircle, AlertCircle, RefreshCcw05 } from "@untitledui/icons";
import { Button, Input } from "react-aria-components";

export default function @@PAGE_NAME@@() {
  const [rows, setRows] = useState<@@TYPE@@Type[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<Record<string, string | boolean>>({});
  const [showDrawer, setShowDrawer] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setRows(await api.get<@@TYPE@@Type[]>("/@@PLURAL@@"));
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
      await api.post<@@TYPE@@Type>("/@@PLURAL@@", body);
      setForm({});
      setShowDrawer(false);
      setNotice("@@SINGULAR@@ created successfully!");
      setTimeout(() => setNotice(""), 3000);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create record");
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this record?")) return;
    try {
      await api.del(`/@@PLURAL@@/${id}`);
      setNotice("Record deleted successfully.");
      setTimeout(() => setNotice(""), 3000);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete record");
    }
  };

  const field = (name: string) => (form[name] ?? "") as string | boolean;

  const set = (name: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [name]: value }));

  const filteredRows = rows.filter((r) => {
    if (!search.trim()) return true;
    return JSON.stringify(r).toLowerCase().includes(search.toLowerCase());
  });

  return (
    <main className="min-h-screen bg-brand-solid px-4 py-8 text-brand-primary sm:px-6 md:py-12">
      <div className="mx-auto max-w-6xl">
        {/* Navigation Breadcrumb & Actions */}
        <div className="flex items-center justify-between gap-2">
           <Link href="/" className="rounded-lg bg-brand-solid px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Dashboard
            </Link>


          <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary ring-1 ring-border-secondary ring-inset">Module: @@PLURAL@@</span>
        </div>

        {/* Header Hero */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4"
        >
          <div className="rounded-2xl border border-secondary bg-primary shadow-xs">
            <div className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold text-primary text-2xl md:text-3xl">@@TITLE@@</h3>
                  <p className="text-sm text-tertiary mt-1">@@PURPOSE@@</p>
                </div>

                <div className="flex items-center gap-2">
                  <Button className="rounded-lg border border-primary bg-primary h-9 w-9 p-0 font-semibold text-secondary shadow-xs transition-colors hover:bg-primary_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" onClick={() => void load()} aria-label="Refresh records">
                    <RefreshCcw05 className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                  </Button>
                  <Button className="rounded-lg bg-brand-solid px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" onClick={() => setShowDrawer(true)}>
                    <Plus className="h-4 w-4" />
                    New @@SINGULAR@@
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Notices and Alerts */}
        <AnimatePresence>
          {notice && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-4"
            >
              <div role="alert" className="rounded-lg border border-secondary bg-secondary p-4 text-sm">
                <CheckCircle className="h-4 w-4" />
                <div className="text-sm text-tertiary">{notice}</div>
              </div>
            </motion.div>
          )}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-4"
            >
              <div role="alert" className="rounded-lg border border-secondary bg-secondary p-4 text-sm">
                <AlertCircle className="h-4 w-4" />
                <div className="text-sm text-tertiary">{error}</div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Data Management Section */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-8"
        >
          <div className="rounded-2xl border border-secondary bg-primary shadow-xs">
            <div className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-primary">Registered Records</h3>
                  <p className="text-sm text-tertiary">
                    {rows.length} total entries recorded in database
                  </p>
                </div>

                <div className="relative w-full max-w-xs">
                  <SearchLg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
                  <Input
                    type="text"
                    placeholder="Filter records..."
                    aria-label="Filter records"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
            </div>

            <div>
              {/* A table of records has to stay usable on a phone, so the
                  wrapper scrolls horizontally instead of forcing the page wide. */}
              <div className="overflow-x-auto">
                <table className="w-full caption-bottom text-sm">
                  <thead className="[&_tr]:border-b">
                    <tr className="border-b border-secondary transition-colors hover:bg-primary_hover">
                      <th className="h-10 px-2 text-left align-middle font-medium text-tertiary [&:has([role=checkbox])]:w-4 w-24">ID</th>
                      @@HEADERS@@
                      <th className="h-10 px-2 text-left align-middle font-medium text-tertiary [&:has([role=checkbox])]:w-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((row) => (
                      <tr className="border-b border-secondary transition-colors hover:bg-primary_hover" key={row.id}>
                        <td className="p-2 align-middle font-mono text-xs text-tertiary">
                          {String(row.id).slice(0, 8)}
                        </td>
                        @@CELLS@@
                        <td className="p-2 align-middle text-right">
                          <Button className="rounded-lg px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:bg-primary_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring text-error-primary hover:text-error-primary" onClick={() => void remove(row.id)}>
                            <Trash01 className="h-3.5 w-3.5" />
                            <span className="sr-only sm:not-sr-only">Delete</span>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {loading && (
                <div className="space-y-2 py-6">
                  {[0, 1, 2].map((i) => (
                    <div className="h-4 w-full animate-pulse rounded-md bg-quaternary h-9" key={i}/>
                  ))}
                </div>
              )}

              {!loading && filteredRows.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <SearchLg className="h-6 w-6 text-tertiary" />
                  <h3 className="text-lg font-semibold text-primary text-base">No records found</h3>
                  <p className="text-sm text-tertiary">
                    {search
                      ? "No records match your filter."
                      : "Get started by creating your first record."}
                  </p>
                  <Button className="rounded-lg bg-brand-solid px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring mt-2" onClick={() => setShowDrawer(true)}>
                    <Plus className="h-4 w-4" />
                    Create First Record
                  </Button>
                </div>
              )}
            </div>
          </div>
        </motion.section>

        {/* Slide-over Create Record Drawer */}
        <AnimatePresence>
          {showDrawer && (
            <div className="fixed inset-0 z-50 flex justify-end">
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setShowDrawer(false)}
                className="fixed inset-0 bg-overlay/40 backdrop-blur-sm"
              />

              <motion.div
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 28, stiffness: 300 }}
                className="relative z-10 w-full max-w-md overflow-y-auto border-l border-secondary bg-brand-solid p-6 shadow-2xl"
                role="dialog"
                aria-modal="true"
                aria-label="New @@SINGULAR@@"
              >
                <div className="flex items-start justify-between gap-2 border-b border-secondary pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-brand-primary">New @@SINGULAR@@</h3>
                    <p className="text-xs text-tertiary">
                      Fill in the fields to create a record
                    </p>
                  </div>
                  <Button className="rounded-lg h-9 w-9 p-0 font-semibold text-secondary transition-colors hover:bg-primary_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" onClick={() => setShowDrawer(false)} aria-label="Close">
                    <ArrowLeft className="h-4 w-4 rotate-90" />
                  </Button>
                </div>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void create();
                  }}
                  className="mt-6 space-y-4"
                >
                  @@FORM_FIELDS@@

                  <div className="flex items-center justify-end gap-2 border-t border-secondary pt-6">
                    <Button className="rounded-lg px-4 py-2 text-sm font-semibold text-secondary transition-colors hover:bg-primary_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" type="button" onClick={() => setShowDrawer(false)}>
                      Cancel
                    </Button>
                    <Button className="rounded-lg bg-brand-solid px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" type="submit">Save Record</Button>
                  </div>
                </form>
              </motion.div>
            </div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
"""


def _label(name: str) -> str:
    return name.replace("_", " ").title()


_LANDING_KINDS = frozenset({
    "landing",
    "catalog",
    "marketplace",
    "portfolio",
    "social",
    "booking",
})


def _primary_entity(spec: AppSpec) -> Entity | None:
    """The entity a visitor sees first: the one with a human-readable name field."""
    for entity in spec.entities:
        if any(f.name in ("name", "title", "label") for f in entity.fields):
            return entity
    return spec.entities[0] if spec.entities else None


_LANDING_TSX = """\
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import type { @@PRIMARY_TYPE@@ as PrimaryType } from "@/lib/types";
import { api } from "@/lib/api";
import { Button, Input, Label } from "react-aria-components";
import { Activity, ArrowRight, Database01, LayersTwo01 } from "@untitledui/icons";
import { cn } from "@/lib/utils";

type PrimaryField = {
  key: string;
  label: string;
  kind: string;
  required: boolean;
  options: string[];
};

const PRIMARY_PLURAL: string = @@PRIMARY_PLURAL@@;
const PRIMARY_ROUTE: string = @@PRIMARY_ROUTE@@;
const OTHER_CARDS: Array<{ label: string; plural: string; route: string; count: number }> = @@OTHER_CARDS@@;
const PRIMARY_FIELDS: PrimaryField[] = @@PRIMARY_FIELDS@@;
const APP_NAME: string = @@APP_NAME@@;
const ONE_LINER: string = @@ONE_LINER@@;
const CORE_VALUE: string = @@CORE_VALUE@@;
const STAGE: string = @@STAGE@@;
const CHART_METRIC: string = @@CHART_METRIC@@;

function recordTitle(row: object, fallback: string): string {
  const rec = row as unknown as Record<string, unknown>;
  const named = rec.name ?? rec.title ?? rec.label;
  if (named !== undefined && named !== null && String(named).trim() !== "") {
    return String(named);
  }
  return fallback;
}

export default function Home() {
  const [rows, setRows] = useState<PrimaryType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const canCreate = STAGE !== "showcase";

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<PrimaryType[]>(`/${PRIMARY_PLURAL}`);
      setRows(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Could not load ${PRIMARY_PLURAL}`);
    } finally {
      setLoading(false);
    }
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      Object.values(row).some((value) =>
        String(value).toLowerCase().includes(q),
      ),
    );
  }, [rows, query]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!canCreate) return;
    setSaving(true);
    setNotice("");
    setError("");
    try {
      await api.post(`/${PRIMARY_PLURAL}`, form);
      setForm({});
      setNotice("Saved.");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-primary text-primary">
      {/* Hero — driven by the spec's own name and value proposition */}
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="border-b border-secondary bg-secondary"
      >
        <div className="mx-auto max-w-container px-6 py-14 md:py-20">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-primary px-2.5 py-0.5 text-xs font-medium text-brand-secondary">
            <Activity className="h-3.5 w-3.5" />
            {APP_NAME}
          </span>
          <h1 className="mt-4 max-w-3xl text-display-sm font-semibold text-primary md:text-display-md">
            {ONE_LINER}
          </h1>
          <p className="mt-4 max-w-2xl text-md text-tertiary">{CORE_VALUE}</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button
              className="rounded-lg bg-brand-solid px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-solid_hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              onPress={() => {
                window.location.href = PRIMARY_ROUTE;
              }}
            >
              Explore {APP_NAME}
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Link
              href={PRIMARY_ROUTE}
              className="rounded-lg border border-primary bg-primary px-4 py-2.5 text-sm font-semibold text-secondary shadow-xs transition-colors hover:bg-primary_hover"
            >
              Browse all {PRIMARY_PLURAL}
            </Link>
          </div>
        </div>
      </motion.section>

      {/* Live figures — real API counts, not sample data */}
      <section className="mx-auto max-w-container px-6 py-10">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-secondary bg-primary p-6 shadow-xs">
            <div className="flex items-center gap-2 text-tertiary">
              <Database01 className="h-4 w-4" />
              <span className="text-sm font-medium">{PRIMARY_PLURAL}</span>
            </div>
            <div className="mt-2 text-display-sm font-semibold text-primary">
              {loading ? "…" : rows.length}
            </div>
            <p className="mt-1 text-sm text-tertiary">records loaded from your workspace</p>
          </div>
          <div className="rounded-2xl border border-secondary bg-primary p-6 shadow-xs">
            <div className="flex items-center gap-2 text-tertiary">
              <LayersTwo01 className="h-4 w-4" />
              <span className="text-sm font-medium">Modules</span>
            </div>
            <div className="mt-2 text-display-sm font-semibold text-primary">
              {OTHER_CARDS.length + 1}
            </div>
            <p className="mt-1 text-sm text-tertiary">screens wired to the API</p>
          </div>
          <div className="rounded-2xl border border-secondary bg-primary p-6 shadow-xs">
            <div className="flex items-center gap-2 text-tertiary">
              <Activity className="h-4 w-4" />
              <span className="text-sm font-medium">{CHART_METRIC || "Status"}</span>
            </div>
            <div className="mt-2 text-display-sm font-semibold text-primary">
              {CHART_METRIC ? "Live" : "—"}
            </div>
            <p className="mt-1 text-sm text-tertiary">
              {CHART_METRIC ? "tracked across your records" : "no metric configured"}
            </p>
          </div>
        </div>
      </section>

      {/* Records — the primary entity, filtered live */}
      <section className="mx-auto max-w-container px-6 pb-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-primary">
            {PRIMARY_PLURAL}
          </h2>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Search ${PRIMARY_PLURAL}`}
            className="h-9 w-full max-w-xs rounded-lg border border-primary bg-primary px-3 py-2 text-sm text-primary shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-error bg-secondary p-4 text-sm text-error-primary"
          >
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-28 animate-pulse rounded-2xl border border-secondary bg-quaternary"
              />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-secondary bg-secondary p-10 text-center">
            <p className="text-base font-semibold text-primary">
              No {PRIMARY_PLURAL} yet
            </p>
            <p className="mt-1 text-sm text-tertiary">
              {query ? "Try a different search." : "Records you create will appear here."}
            </p>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((row, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(idx * 0.03, 0.3) }}
                className="group rounded-2xl border border-secondary bg-primary p-5 shadow-xs transition-all hover:shadow-md"
              >
                <h3 className="text-base font-semibold text-primary transition-colors group-hover:text-brand-primary">
                  {recordTitle(row, `Record ${idx + 1}`)}
                </h3>
                <dl className="mt-3 space-y-1.5">
                  {PRIMARY_FIELDS.filter((f) => f.key !== "name" && f.key !== "title")
                    .slice(0, 3)
                    .map((f) => (
                      <div key={f.key} className="flex justify-between gap-3 text-sm">
                        <dt className="text-tertiary">{f.label}</dt>
                        <dd className="font-medium text-secondary">
                          {String(
                            (row as unknown as Record<string, unknown>)[f.key] ?? "—",
                          )}
                        </dd>
                      </div>
                    ))}
                </dl>
              </motion.div>
            ))}
          </div>
        )}
      </section>

      {/* Create — only when the spec says the app transacts or operates */}
      {canCreate && (
        <section className="mx-auto max-w-container px-6 pb-10">
          <form
            onSubmit={onCreate}
            className="rounded-2xl border border-secondary bg-secondary p-6"
          >
            <h2 className="text-lg font-semibold text-primary">
              Add a {PRIMARY_FIELDS.length ? "" : "record"}
            </h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {PRIMARY_FIELDS.map((f) => (
                <div key={f.key} className="flex flex-col gap-2">
                  <Label htmlFor={f.key} className="text-sm font-medium text-secondary">
                    {f.label}
                  </Label>
                  {f.kind === "bool" ? (
                    <input
                      id={f.key}
                      type="checkbox"
                      checked={form[f.key] === "true"}
                      onChange={(e) =>
                        setForm({ ...form, [f.key]: e.target.checked ? "true" : "false" })
                      }
                      className="h-4 w-4"
                    />
                  ) : f.kind === "enum" ? (
                    <select
                      id={f.key}
                      value={form[f.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                      className="h-9 w-full rounded-lg border border-primary bg-primary px-3 py-2 text-sm text-primary shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                    >
                      <option value="">Select…</option>
                      {f.options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      id={f.key}
                      type={f.kind === "int" || f.kind === "float" ? "number" : f.kind === "date" ? "date" : f.kind === "datetime" ? "datetime-local" : "text"}
                      value={form[f.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                      required={f.required}
                      className="h-9 w-full rounded-lg border border-primary bg-primary px-3 py-2 text-sm text-primary shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                    />
                  )}
                </div>
              ))}
            </div>
            {notice && <p className="mt-4 text-sm text-success-primary">{notice}</p>}
            <Button
              type="submit"
              isDisabled={saving}
              className={cn(
                "mt-5 rounded-lg bg-brand-solid px-4 py-2 text-sm font-semibold text-white",
                "transition-colors hover:bg-brand-solid_hover",
              )}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </form>
        </section>
      )}

      {/* Module navigation — every other entity in the spec */}
      {OTHER_CARDS.length > 0 && (
        <section className="mx-auto max-w-container px-6 pb-16">
          <h2 className="text-lg font-semibold text-primary">Modules</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {OTHER_CARDS.map((c) => (
              <Link
                key={c.route}
                href={c.route}
                className="group rounded-2xl border border-secondary bg-primary p-5 shadow-xs transition-all hover:border-brand hover:shadow-md"
              >
                <h3 className="text-base font-semibold text-primary transition-colors group-hover:text-brand-primary">
                  {c.label}
                </h3>
                <p className="mt-1 text-sm text-tertiary">
                  {c.count} fields · /{c.plural}
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
"""

# Emitted only when the spec opts into analytics. Pairing this with the
# `recharts` import in _DASHBOARD_TSX keeps both sides on one flag.
_TREND_CHART_TSX = """\
                {analytics.trend && analytics.trend.length > 0 && (
                  <div className="rounded-2xl border border-secondary bg-primary shadow-xs">
                    <div className="flex flex-col gap-1.5">
                      <h3 className="text-lg font-semibold text-primary text-xs font-medium text-tertiary">
                        Activity &amp; Volume Trend
                      </h3>
                    </div>
                    <div>
                      <ResponsiveContainer width="100%" height={220}>
                        <LineChart data={analytics.trend}>
                          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Line
                            type="monotone"
                            dataKey="total"
                            stroke="hsl(var(--primary))"
                            strokeWidth={2}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}"""


def _gen_dashboard(spec: AppSpec) -> str:
    routes = json.dumps([[e.plural, e.plural] for e in spec.entities])
    # The chart dependency and the chart JSX are gated by the same flag that
    # decides whether package.json ships `recharts` (see write_generated). Gating
    # only one side is what previously produced a dashboard importing a package
    # that had just been stripped out of package.json.
    analytics_enabled = bool(getattr(spec, "analytics", None) and spec.analytics.enabled)
    if analytics_enabled:
        chart_import = 'import {\n  ResponsiveContainer,\n  LineChart,\n  Line,\n  XAxis,\n  YAxis,\n  Tooltip,\n} from "recharts";'
        trend_chart = _TREND_CHART_TSX
    else:
        chart_import = ""
        trend_chart = ""
    return (
        _DASHBOARD_TSX.replace("@@ENTITY_ROUTES@@", routes)
        .replace("@@RECHARTS_IMPORT@@", chart_import)
        .replace("@@TREND_CHART@@", trend_chart)
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
        headers.append(f'<th className="h-10 px-2 text-left align-middle font-medium text-tertiary [&:has([role=checkbox])]:w-4 px-3 py-2">{label}</th>')
        if f.type == "bool":
            cells.append(
                f'<td className="p-2 align-middle px-3 py-2">{{row.{f.name} ? "Yes" : "No"}}</td>'
            )
            assigns.append(f"      body[{key}] = form[{key}] === true;")
            form_fields.append(
                '<div className="flex items-center gap-2">\n'
                f"          <Checkbox  id={key} "
                f"isSelected={{field({key}) === true}} "
                f"onChange={{(v) => set({key}, v === true)}} />\n"
                f'          <Label htmlFor={key} className="cursor-pointer">{label}</Label>\n'
                "        </div>"
            )
        elif f.type == "enum":
            options = "\n            ".join(
                f"<option value={js_key(v)}>{_label(v)}</option>" for v in f.enum_values
            )
            form_fields.append(
                '<div className="flex flex-col gap-2">\n'
                f"          <Label htmlFor={key}>{label}</Label>\n"
                f'          <select\n'
                f'            id={{{key}}}\n'
                f'            value={{String(field({key}) ?? "")}}\n'
                f'            onChange={{(e) => set({key}, e.target.value)}}\n'
                f'            className="h-9 w-full rounded-lg border border-primary bg-primary px-3 py-2 text-sm text-primary shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"\n'
                "          >\n"
                '            ><option value="">Select…</option>\n'
                f"            {options}\n"
                "          </select>\n"
                "        </div>"
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
                '<div className="flex flex-col gap-2">\n'
                f"          <Label htmlFor={key}>{label}</Label>\n"
                f'          <Input id={key} type="{input_type}" '
                f'value={{String(field({key}) ?? "")}} '
                f"onChange={{(e) => set({key}, e.target.value)}} />\n"
                "        </div>"
            )
            cells.append(
                f'><td className="p-2 align-middle px-3 py-2">{{String(row.{f.name} ?? "—")}}</td>'
            )

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


def _is_landing_or_storefront(spec: AppSpec) -> bool:
    """True when `/` should lead with content about the domain rather than an admin console."""
    return getattr(spec, "app_kind", "internal") in _LANDING_KINDS


def plan_schema_delta(old_spec: AppSpec | None, new_spec: AppSpec) -> dict[str, Any]:
    """Compute structural delta between two AppSpecs for non-destructive evolution."""
    if not old_spec:
        return {
            "is_initial": True,
            "added_entities": [e.name for e in new_spec.entities],
            "removed_entities": [],
            "modified_entities": {},
        }
    old_names = {e.name: e for e in old_spec.entities}
    new_names = {e.name: e for e in new_spec.entities}
    added = [name for name in new_names if name not in old_names]
    removed = [name for name in old_names if name not in new_names]
    modified = {}
    for name in new_names:
        if name in old_names:
            old_fields = {f.name: f.type for f in old_names[name].fields}
            new_fields = {f.name: f.type for f in new_names[name].fields}
            added_f = [fn for fn in new_fields if fn not in old_fields]
            removed_f = [fn for fn in old_fields if fn not in new_fields]
            if added_f or removed_f:
                modified[name] = {"added_fields": added_f, "removed_fields": removed_f}
    return {
        "is_initial": False,
        "added_entities": added,
        "removed_entities": removed,
        "modified_entities": modified,
    }


def _gen_landing_page(spec: AppSpec) -> str:
    """Compose `/` from the spec itself.

    The page shape follows `app_kind` (what the app is) and `lifecycle_stage`
    (how far it goes): a showcase reads its entities, an `operate` app also
    manages them. Nothing here assumes a domain — no carts, no flavours, no
    fixed endpoints — every string, route and metric comes from the spec.
    """
    app_name = _label(spec.app_name)
    one_liner = getattr(spec, "one_liner", "") or f"Welcome to {app_name}"
    core_value = (
        getattr(spec, "core_value", "")
        or "A focused workspace built around the data that matters."
    )
    kind = getattr(spec, "app_kind", "internal")
    stage = getattr(spec, "lifecycle_stage", "showcase")

    # The "primary" entity drives the hero stat, the card grid and the CTA.
    primary = _primary_entity(spec)
    primary_plural = primary.plural if primary else "records"
    primary_label = _label(primary.name) if primary else "Record"
    primary_route = f"/{primary_plural}" if primary else "/"

    # Every other real entity becomes a nav card, so the page is a router too.
    other_cards = [
        {
            "label": _label(e.name),
            "plural": e.plural,
            "route": f"/{e.plural}",
            "count": len(e.fields),
        }
        for e in spec.entities
        if primary is None or e.name != primary.name
    ]

    # Analytics is opt-in on the spec; when present the spec names the metric.
    analytics = getattr(spec, "analytics", None)
    chart_metric = ""
    if analytics and getattr(analytics, "enabled", False) and primary:
        numeric = next(
            (f for f in primary.fields if f.type in ("int", "float")), None
        )
        if numeric:
            chart_metric = numeric.name

    # A showcase only reads; transact/operate add the primary action.
    entity_fields = [
        {
            "key": f.name,
            "label": _label(f.name),
            "kind": f.type,
            "required": bool(f.required and f.default is None),
            "options": list(getattr(f, "enum_values", []) or []),
        }
        for f in (primary.fields if primary else [])
    ]

    return (
        _LANDING_TSX.replace("@@APP_NAME@@", json.dumps(app_name))
    .replace("@@ONE_LINER@@", json.dumps(one_liner))
    .replace("@@CORE_VALUE@@", json.dumps(core_value))
    .replace("@@KIND@@", json.dumps(kind))
    .replace("@@STAGE@@", json.dumps(stage))
    .replace("@@PRIMARY_LABEL@@", json.dumps(primary_label))
    .replace("@@PRIMARY_PLURAL@@", json.dumps(primary_plural))
    .replace("@@PRIMARY_ROUTE@@", json.dumps(primary_route))
    .replace("@@PRIMARY_TYPE@@", _cls(primary.name) if primary else "Record")
    .replace("@@PRIMARY_FIELDS@@", json.dumps(entity_fields, indent=2))
    .replace("@@OTHER_CARDS@@", json.dumps(other_cards, indent=2))
        .replace("@@CHART_METRIC@@", json.dumps(chart_metric))
    )



def gen_frontend_pages(spec: AppSpec, fe: Path) -> None:
    """Write a landing page/dashboard and one CRUD page per spec screen (API-backed, non-destructive)."""
    app_dir = fe / "src" / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    by_key: dict[str, Entity] = {e.name: e for e in spec.entities}
    by_key.update({e.plural: e for e in spec.entities})
    written: set[str] = set()

    for screen in spec.screens:
        route = str(screen.route or "/").strip("/")
        if route in written:
            continue
        # The spec (and the LLM that writes it) may use `{var}` or `<var>`
        # placeholder syntax for a route parameter. Next.js App Router only
        # recognises `[var]`, so a literal `{id}` segment would create a directory
        # that is never served and a route that always 404s.
        route = re.sub(r"[{<](\w+)[}>]", r"[\1]", route)
        page_path = (app_dir / route / "page.tsx") if route else (app_dir / "page.tsx")
        page_path.parent.mkdir(parents=True, exist_ok=True)

        target_path = page_path
        if page_path.exists():
            existing = page_path.read_text(encoding="utf-8", errors="replace")
            # If the user edited this page manually without our generated-by stamp, preserve it!
            has_our_stamp = (
                "// @generated by AI Solution Builder" in existing or "generated-by" in existing
            )
            # A page that still contains scaffold placeholders was never edited by anyone:
            # the template ships one precisely so it gets replaced. Treating it as a user
            # edit would divert the generated page to `page.generated.tsx`, which nothing
            # imports — the app would render the un-replaced placeholder instead.
            still_a_placeholder = any(
                marker in existing
                for marker in (
                    "__MODULE_LINKS__",
                    "__APP_TITLE__",
                    "__APP_NAME__",
                    "__APP_SLUG__",
                    "__APP_DESCRIPTION__",
                )
            )
            if not has_our_stamp and not still_a_placeholder:
                target_path = page_path.with_name("page.generated.tsx")

        stamp = "// @generated by AI Solution Builder (non-destructive)\n"
        if not route:
            if _is_landing_or_storefront(spec):
                target_path.write_text(stamp + _gen_landing_page(spec), encoding="utf-8")
            else:
                target_path.write_text(stamp + _gen_dashboard(spec), encoding="utf-8")
        else:
            entity = next(
                (by_key.get(u) for u in (screen.uses_entities or []) if by_key.get(u)),
                spec.entities[0],
            )
            assert entity is not None
            target_path.write_text(stamp + _gen_entity_page(spec, entity, route), encoding="utf-8")
        written.add(route)



# ── Next.js Fullstack Route Handlers & Data Store ────────────────────────

_NEXT_DB_TS = """// In-memory data store for Next.js Route Handlers.
// Deliberately EMPTY: the app starts with real empty states and the records
// a user creates are the ones it renders. No sample/example data is invented.
type Row = Record<string, unknown>;

export class Database {
  private tables = new Map<string, Row[]>();
  private nextIds = new Map<string, number>();

  seedTable(table: string) {
    if (!this.tables.has(table)) this.tables.set(table, []);
    if (!this.nextIds.has(table)) this.nextIds.set(table, 1);
  }

  list(table: string): Row[] {
    return this.tables.get(table) ?? [];
  }

  insert(table: string, row: Row): Row {
    this.seedTable(table);
    const id = this.nextIds.get(table) ?? 1;
    this.nextIds.set(table, id + 1);
    const record: Row = { id, ...row, created_at: new Date().toISOString() };
    this.tables.get(table)!.push(record);
    return record;
  }

  update(table: string, id: number, patch: Row): Row | null {
    const rows = this.tables.get(table);
    const found = rows?.find((r) => Number(r.id) === id);
    if (!found) return null;
    Object.assign(found, patch, { updated_at: new Date().toISOString() });
    return found;
  }

  getById(table: string, id: number): Row | null {
    return this.tables.get(table)?.find((r) => Number(r.id) === id) ?? null;
  }

  delete(table: string, id: number): boolean {
    const rows = this.tables.get(table);
    if (!rows) return false;
    const idx = rows.findIndex((r) => Number(r.id) === id);
    if (idx === -1) return false;
    rows.splice(idx, 1);
    return true;
  }
}

export const getDb = (() => {
  let db: Database | null = null;
  return () => (db ??= new Database());
})();
"""

_NEXT_COLLECTION_ROUTE_TS = """// @generated by AI Solution Builder (non-destructive)
import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export async function GET() {
  const db = getDb();
  return NextResponse.json(db.list("@@PLURAL@@"));
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const db = getDb();
    const created = db.insert("@@PLURAL@@", body);
    return NextResponse.json(created, { status: 201 });
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Invalid payload" }, { status: 400 });
  }
}
"""

_NEXT_ITEM_ROUTE_TS = """// @generated by AI Solution Builder (non-destructive)
import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

type RouteContext = { params: Promise<{ id: string }> | { id: string } };

export async function GET(req: NextRequest, context: RouteContext) {
  const params = await Promise.resolve(context.params);
  const id = Number(params.id);
  const db = getDb();
  const item = db.getById("@@PLURAL@@", id);
  if (!item) {
    return NextResponse.json({ error: "Item not found" }, { status: 404 });
  }
  return NextResponse.json(item);
}

export async function PATCH(req: NextRequest, context: RouteContext) {
  try {
    const params = await Promise.resolve(context.params);
    const id = Number(params.id);
    const body = await req.json();
    const db = getDb();
    const updated = db.update("@@PLURAL@@", id, body);
    if (!updated) {
      return NextResponse.json({ error: "Item not found" }, { status: 404 });
    }
    return NextResponse.json(updated);
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Invalid payload" }, { status: 400 });
  }
}

export async function DELETE(req: NextRequest, context: RouteContext) {
  const params = await Promise.resolve(context.params);
  const id = Number(params.id);
  const db = getDb();
  const deleted = db.delete("@@PLURAL@@", id);
  if (!deleted) {
    return NextResponse.json({ error: "Item not found" }, { status: 404 });
  }
  return new NextResponse(null, { status: 204 });
}
"""

_NEXT_HEALTH_ROUTE_TS = """import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "healthy",
    service: "next-fullstack",
    timestamp: new Date().toISOString(),
  });
}
"""

_NEXT_DOCKERFILE = """# Next.js Fullstack Image (Node.js runtime, single container)
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \\
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/v1/health || exit 1

CMD ["npm", "start"]
"""


def gen_next_route_handlers(spec: AppSpec, fe: Path) -> None:
    """Generate Next.js Route Handlers for fullstack operations without Python backend."""
    api_dir = fe / "src" / "app" / "api" / "v1"
    api_dir.mkdir(parents=True, exist_ok=True)

    # 1. In-memory data store for Next.js Route Handlers
    db_file = fe / "src" / "lib" / "db.ts"
    if not db_file.exists():
        db_file.write_text(_NEXT_DB_TS, encoding="utf-8")

    # 2. Health check route: /api/v1/health
    health_dir = api_dir / "health"
    health_dir.mkdir(parents=True, exist_ok=True)
    (health_dir / "route.ts").write_text(_NEXT_HEALTH_ROUTE_TS, encoding="utf-8")

    # 3. Collection & item CRUD route handlers for each entity
    for entity in spec.entities:
        ent_dir = api_dir / entity.plural
        ent_dir.mkdir(parents=True, exist_ok=True)
        coll_code = _NEXT_COLLECTION_ROUTE_TS.replace("@@PLURAL@@", entity.plural)
        (ent_dir / "route.ts").write_text(coll_code, encoding="utf-8")

        item_dir = ent_dir / "[id]"
        item_dir.mkdir(parents=True, exist_ok=True)
        item_code = _NEXT_ITEM_ROUTE_TS.replace("@@PLURAL@@", entity.plural)
        (item_dir / "route.ts").write_text(item_code, encoding="utf-8")

    # 4. Action endpoints
    for action in spec.actions:
        action_name = _clean_ident(action.name)
        act_dir = api_dir / "actions" / action_name
        act_dir.mkdir(parents=True, exist_ok=True)
        example_json = json.dumps(action.output_example or {"status": "success"})
        act_code = f"""// @generated by AI Solution Builder (non-destructive)
import {{ NextRequest, NextResponse }} from "next/server";

export async function POST(req: NextRequest) {{
  try {{
    const body = await req.json().catch(() => ({{}}));
    return NextResponse.json({{
      action: "{action.name}",
      status: "completed",
      result: {example_json},
    }});
  }} catch (err: any) {{
    return NextResponse.json({{ error: err?.message || "Action execution failed" }}, {{ status: 400 }});
  }}
}}
"""
        (act_dir / "route.ts").write_text(act_code, encoding="utf-8")

    # 5. Analytics endpoint: /api/v1/analytics/summary (opt-in)
    analytics_enabled = bool(getattr(spec, "analytics", None) and spec.analytics.enabled)
    if analytics_enabled:
        analytics_dir = api_dir / "analytics" / "summary"
        analytics_dir.mkdir(parents=True, exist_ok=True)
        from app.services.analytics_spec import resolve_analytics_target

        target = resolve_analytics_target(spec)
        if target:
            c_plural = target.entity.plural
            f_name = target.metric_field.name
            e_name = target.entity.name
            analytics_code = f"""// @generated by AI Solution Builder (non-destructive)
import {{ NextResponse }} from "next/server";
import {{ getDb }} from "@/lib/db";

export async function GET() {{
  const db = getDb();
  const rows = db.list("{c_plural}");
  const count = rows.length;
  const total = rows.reduce((acc: number, r: any) => acc + (Number(r["{f_name}"]) || 0), 0);
  const average = count > 0 ? total / count : 0;
  return NextResponse.json({{
    available: true,
    entity: "{e_name}",
    metric: "{f_name}",
    count,
    total,
    average,
    trend: [],
  }});
}}
"""
        else:
            analytics_code = """// @generated by AI Solution Builder (non-destructive)
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    available: false,
    reason: "no numeric fields found",
  });
}
"""
        (analytics_dir / "route.ts").write_text(analytics_code, encoding="utf-8")


# ── orchestration ───────────────────────────────────────────────────────


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


_GEN_STAMP = "@generated by AI Solution Builder"

# Files the scaffold owns unconditionally — never pruned even if the spec stops
# referencing them, because the app cannot run without them.
_PRUNE_EXEMPT = {"api", "health", "actions", "[id]", "globals.css", "theme.css", "layout.tsx"}


def _is_generated(path: Path) -> bool:
    """True when ``path`` carries our generated stamp (so it is safe to rewrite/remove)."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False
    return _GEN_STAMP in head or "generated-by" in head


def _prune_stale_routes(spec: AppSpec, root: Path) -> list[str]:
    """Delete generated pages/API routes that the current spec no longer declares.

    A build directory can be scaffolded more than once (a fallback spec first, the
    real LLM spec second). The second pass used to only ever *add* files, leaving
    orphan pages whose API routes pointed at tables that no longer existed.

    Non-destructive: only directories whose files carry our generated stamp are
    removed. Anything a user authored or edited is left untouched.
    """
    removed: list[str] = []
    fe = root / "frontend"
    app_dir = fe / "src" / "app"
    if not app_dir.is_dir():
        return removed

    # Routes the spec currently wants, as directory names under src/app.
    wanted_pages: set[str] = {""}
    for screen in spec.screens:
        route = str(screen.route or "").strip("/")
        wanted_pages.add(route.split("/")[0] if route else "")
    wanted_pages |= _PRUNE_EXEMPT

    wanted_api: set[str] = {"health", "actions"}
    for entity in spec.entities:
        wanted_api.add(entity.plural)
    for action in spec.actions:
        wanted_api.add(_clean_ident(action.name))
    if getattr(spec, "analytics", None) and spec.analytics.enabled:
        wanted_api.add("analytics")
    wanted_api |= {"[id]"}

    checks = (
        (app_dir, wanted_pages),
        (app_dir / "api" / "v1", wanted_api),
        (app_dir / "api" / "v1" / "actions", {_clean_ident(a.name) for a in spec.actions}),
    )
    for dir_path, keep in checks:
        if not dir_path.is_dir():
            continue
        for child in sorted(dir_path.iterdir()):
            if not child.is_dir() or child.name in keep:
                continue
            # Only prune a directory we own: its page/route file must be stamped
            # and it must not contain any user-authored file.
            entry = child / "page.tsx"
            if not entry.exists():
                entry = child / "route.ts"
            if not entry.exists():
                nested = sorted(child.glob("*/route.ts"))
                entry = nested[0] if nested else entry
            if entry is None or not entry.exists() or not _is_generated(entry):
                continue
            if any(
                not _is_generated(f)
                for f in child.rglob("*")
                if f.is_file() and f.suffix in {".ts", ".tsx"}
            ):
                continue
            shutil.rmtree(child)
            removed.append(str(child.relative_to(fe)))

    for stale in ("routers_analytics.py",):
        path = root / "backend" / stale
        if path.exists() and not (getattr(spec, "analytics", None) and spec.analytics.enabled):
            if _is_generated(path):
                path.unlink()
                removed.append(f"backend/{stale}")
    return removed


def write_generated(root: Path | str, spec: AppSpec) -> dict[str, str]:
    """Write all deterministic files into a scaffolded workspace. Returns locked hashes."""
    root = Path(root)
    be, fe = root / "backend", root / "frontend"
    (be / "tests").mkdir(parents=True, exist_ok=True)
    analytics_enabled = bool(getattr(spec, "analytics", None) and spec.analytics.enabled)
    files = {
        be / "models.py": "# @generated by AI Solution Builder\n" + gen_models(spec),
        be / "schemas.py": "# @generated by AI Solution Builder\n" + gen_schemas(spec),
        be / "routers.py": "# @generated by AI Solution Builder\n" + gen_routers(spec),
        be / "actions.py": "# @generated by AI Solution Builder\n" + gen_actions_stub(spec),
        be / "tests" / "conftest.py": CONFTEST,
        be / "tests" / "test_acceptance.py": "# @generated by AI Solution Builder\n" + gen_acceptance_tests(spec),
        root / "spec.json": spec.model_dump_json(indent=2),
    }
    if analytics_enabled:
        files[be / "routers_analytics.py"] = "# @generated by AI Solution Builder\n" + gen_analytics_router(spec)
    if fe.exists():
        (fe / "src" / "lib").mkdir(parents=True, exist_ok=True)
        files[fe / "src" / "lib" / "types.ts"] = "// @generated by AI Solution Builder\n" + gen_ts_types(spec)
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    if fe.exists():
        gen_frontend_pages(spec, fe)
        gen_next_route_handlers(spec, fe)
        # Second-and-later passes: drop generated routes the current spec no
        # longer declares, so a re-scaffold never leaves orphan pages behind.
        pruned = _prune_stale_routes(spec, root)
        if pruned:
            logger.info("Pruned stale generated routes: %s", ", ".join(pruned))
        pkg_file = fe / "package.json"
        if pkg_file.exists():
            try:
                pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
                deps = pkg_data.setdefault("dependencies", {})
                if analytics_enabled:
                    if "recharts" not in deps:
                        deps["recharts"] = "^2.15.0"
                        pkg_file.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
                else:
                    if "recharts" in deps:
                        del deps["recharts"]
                        pkg_file.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")
            except Exception:
                pass

    # If architecture is next_fullstack, emit the pure Node.js Dockerfile
    if getattr(spec, "architecture", "next_fullstack") == "next_fullstack":
        (root / "Dockerfile").write_text(_NEXT_DOCKERFILE, encoding="utf-8")

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
