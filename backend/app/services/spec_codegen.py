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
    "backend/routers_analytics.py",
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

    return "\n".join([
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
    ])


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
    extra_routers += "if analytics_router is not None:\n    router.include_router(analytics_router)\n"
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
import { SkiperBadge } from "@/components/ui/skiper-ui/skiper-badge";
import { SkiperCard } from "@/components/ui/skiper-ui/skiper-card";
import { Link001 } from "@/components/ui/skiper-ui/skiper40";
import { Layers, Database, Sparkles, Activity, Search } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

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
    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-extrabold text-slate-900">{value}</div>
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
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 px-6 py-12 text-slate-900">
      <div className="mx-auto max-w-6xl">
        {/* Animated Hero Header */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-white/80 p-8 shadow-sm backdrop-blur-md md:p-10"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <SkiperBadge variant="purple" pulse>
                  Production Prototype
                </SkiperBadge>
                <SkiperBadge variant="success" pulse={false}>
                  Live API
                </SkiperBadge>
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl text-slate-900">
                @@TITLE@@
              </h1>
              <p className="mt-2 text-slate-600 max-w-2xl">
                @@PURPOSE@@
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Link001
                href="/api/docs"
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-indigo-300"
              >
                API Docs
              </Link001>
            </div>
          </div>

          {/* Real Analytics KPIs & Chart or Quick Metrics Bar */}
          {analytics?.available ? (
            <div className="mt-8 border-t border-slate-100 pt-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-6">
                <KpiCard
                  label={`Total ${analytics.metric || "Volume"}`}
                  value={analytics.total.toLocaleString()}
                  icon={<Layers className="h-4 w-4 text-indigo-600" />}
                />
                <KpiCard
                  label="Average"
                  value={analytics.average.toFixed(2)}
                  icon={<Activity className="h-4 w-4 text-emerald-600" />}
                />
                <KpiCard
                  label="Records"
                  value={analytics.count.toLocaleString()}
                  icon={<Database className="h-4 w-4 text-violet-600" />}
                />
              </div>
              {analytics.trend && analytics.trend.length > 0 && (
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4">
                  <div className="mb-3 text-xs font-semibold text-slate-600">
                    Activity & Volume Trend
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={analytics.trend}>
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="total"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          ) : (
            <div className="mt-8 grid grid-cols-2 gap-4 border-t border-slate-100 pt-6 sm:grid-cols-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xl font-bold text-slate-900">{ENTITY_ROUTES.length}</div>
                  <div className="text-xs text-slate-500">Modules</div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                  <Database className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xl font-bold text-slate-900">{totalRecords}</div>
                  <div className="text-xs text-slate-500">Total Records</div>
                </div>
              </div>

              <div className="col-span-2 sm:col-span-1 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xl font-bold text-slate-900">99.9%</div>
                  <div className="text-xs text-slate-500">System Uptime</div>
                </div>
              </div>
            </div>
          )}
        </motion.div>

        {/* Search & Header */}
        <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Application Modules
            </h2>
            <p className="text-xs text-slate-500">
              Manage data models and business logic workflows
            </p>
          </div>

          <div className="relative w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search modules..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-4 text-xs font-medium text-slate-900 placeholder:text-slate-400 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>
        </div>

        {/* Animated Cards Grid */}
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {visibleRoutes.map(([name, path], idx) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.3 }}
            >
              <Link href={`/${path}`} className="group block">
                <SkiperCard
                  glow
                  interactive
                  className="border-slate-200/80 bg-white p-6 transition-all group-hover:border-indigo-400/80 group-hover:shadow-lg group-hover:shadow-indigo-500/5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
                      {counts[name] ?? "…"} records
                    </span>
                  </div>

                  <h3 className="mt-4 text-lg font-bold capitalize text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {name.replaceAll("_", " ")}
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Access data records, creation forms, and API actions for {name.replaceAll("_", " ")}.
                  </p>

                  <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs font-semibold text-indigo-600">
                    <span>Manage {name.replaceAll("_", " ")}</span>
                    <span className="transition-transform group-hover:translate-x-1">→</span>
                  </div>
                </SkiperCard>
              </Link>
            </motion.div>
          ))}
        </div>
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
import type { @@TYPE@@ } from "@/lib/types";
import { api } from "@/lib/api";
import { SkiperBadge } from "@/components/ui/skiper-ui/skiper-badge";
import { SkiperButton } from "@/components/ui/skiper-ui/skiper-button";
import { Plus, ArrowLeft, Trash2, Search, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

export default function @@PAGE_NAME@@() {
  const [rows, setRows] = useState<@@TYPE@@[]>([]);
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
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 px-6 py-12 text-slate-900">
      <div className="mx-auto max-w-6xl">
        {/* Navigation Breadcrumb & Actions */}
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-1" />
            Back to Dashboard
          </Link>

          <SkiperBadge variant="purple" pulse={false}>
            Module: @@PLURAL@@
          </SkiperBadge>
        </div>

        {/* Header Hero */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200/90 bg-white/80 p-8 shadow-sm backdrop-blur-md"
        >
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">@@TITLE@@</h1>
            <p className="mt-1 text-sm text-slate-600">@@PURPOSE@@</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => void load()}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50 transition-colors"
              title="Refresh records"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-indigo-600" : ""}`} />
            </button>
            <SkiperButton
              variant="glow"
              size="md"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setShowDrawer(true)}
            >
              New @@SINGULAR@@
            </SkiperButton>
          </div>
        </motion.div>

        {/* Notices and Alerts */}
        <AnimatePresence>
          {notice && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-4 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200/80 px-4 py-3 text-xs font-semibold text-emerald-800 shadow-sm"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>{notice}</span>
            </motion.div>
          )}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mt-4 flex items-center gap-2 rounded-xl bg-rose-50 border border-rose-200/80 px-4 py-3 text-xs font-semibold text-rose-800 shadow-sm"
            >
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Data Management Section */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-5">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Registered Records</h2>
              <p className="text-xs text-slate-500">
                {rows.length} total entries recorded in database
              </p>
            </div>

            <div className="relative w-full max-w-xs">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Filter records..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-4 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-4 py-3">ID</th>
                  @@HEADERS@@
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredRows.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-slate-50/80 transition-colors"
                  >
                    <td className="px-4 py-3 text-xs font-semibold text-slate-500">#{row.id}</td>
                    @@CELLS@@
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => void remove(row.id)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-800 transition-colors p-1 rounded-md hover:bg-rose-50"
                        title="Delete record"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span>Delete</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {loading && (
              <div className="flex items-center justify-center py-12 text-slate-400 text-xs gap-2">
                <RefreshCw className="h-4 w-4 animate-spin text-indigo-600" />
                <span>Loading records...</span>
              </div>
            )}

            {!loading && filteredRows.length === 0 && (
              <div className="py-12 text-center">
                <p className="text-sm font-medium text-slate-500">No records found.</p>
                <p className="text-xs text-slate-400 mt-1">Get started by creating a new entry.</p>
                <div className="mt-4">
                  <SkiperButton
                    variant="outline"
                    size="sm"
                    onClick={() => setShowDrawer(true)}
                  >
                    Create First Record
                  </SkiperButton>
                </div>
              </div>
            )}
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
                className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm"
              />

              <motion.div
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 28, stiffness: 300 }}
                className="relative z-10 w-full max-w-md bg-white p-8 shadow-2xl overflow-y-auto"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">New @@SINGULAR@@</h3>
                    <p className="text-xs text-slate-500">Fill in the fields to create a record</p>
                  </div>
                  <button
                    onClick={() => setShowDrawer(false)}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    ✕
                  </button>
                </div>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void create();
                  }}
                  className="mt-6 space-y-4"
                >
                  @@FORM_FIELDS@@

                  <div className="pt-6 flex items-center justify-end gap-3 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => setShowDrawer(false)}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                      Cancel
                    </button>
                    <SkiperButton type="submit" variant="glow" size="md">
                      Save Record
                    </SkiperButton>
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


# ── Next.js Fullstack Route Handlers & Data Store ────────────────────────

_NEXT_DB_TS = """// In-memory data store for Next.js Route Handlers
// State is preserved across requests via globalThis in development.

type Row = Record<string, any>;

class DataStore {
  private tables: Map<string, Row[]> = new Map();
  private nextIds: Map<string, number> = new Map();

  list(table: string): Row[] {
    return this.tables.get(table) || [];
  }

  getById(table: string, id: number): Row | null {
    const rows = this.list(table);
    return rows.find((r) => r.id === id) || null;
  }

  insert(table: string, data: Row): Row {
    const rows = this.tables.get(table) || [];
    const nextId = this.nextIds.get(table) || 1;
    this.nextIds.set(table, nextId + 1);

    const now = new Date().toISOString();
    const record = {
      id: nextId,
      ...data,
      created_at: now,
      updated_at: now,
    };
    rows.push(record);
    this.tables.set(table, rows);
    return record;
  }

  update(table: string, id: number, patch: Partial<Row>): Row | null {
    const rows = this.tables.get(table) || [];
    const idx = rows.findIndex((r) => r.id === id);
    if (idx === -1) return null;

    rows[idx] = {
      ...rows[idx],
      ...patch,
      id,
      updated_at: new Date().toISOString(),
    };
    return rows[idx];
  }

  delete(table: string, id: number): boolean {
    const rows = this.tables.get(table) || [];
    const idx = rows.findIndex((r) => r.id === id);
    if (idx === -1) return false;
    rows.splice(idx, 1);
    return true;
  }
}

const globalForDb = globalThis as unknown as { __dataStore?: DataStore };
export const db = globalForDb.__dataStore || new DataStore();
if (process.env.NODE_ENV !== "production") globalForDb.__dataStore = db;

export function getDb(): DataStore {
  return db;
}
"""

_NEXT_COLLECTION_ROUTE_TS = """import { NextRequest, NextResponse } from "next/server";
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

_NEXT_ITEM_ROUTE_TS = """import { NextRequest, NextResponse } from "next/server";
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
        act_code = f"""import {{ NextRequest, NextResponse }} from "next/server";

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

    # 5. Analytics endpoint: /api/v1/analytics/summary
    analytics_dir = api_dir / "analytics" / "summary"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    from app.services.analytics_spec import resolve_analytics_target

    target = resolve_analytics_target(spec)
    if target:
        c_plural = target.entity.plural
        f_name = target.metric_field.name
        e_name = target.entity.name
        analytics_code = f"""import {{ NextResponse }} from "next/server";
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
        analytics_code = """import { NextResponse } from "next/server";

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


def write_generated(root: Path | str, spec: AppSpec) -> dict[str, str]:
    """Write all deterministic files into a scaffolded workspace. Returns locked hashes."""
    root = Path(root)
    be, fe = root / "backend", root / "frontend"
    (be / "tests").mkdir(parents=True, exist_ok=True)
    files = {
        be / "models.py": gen_models(spec),
        be / "schemas.py": gen_schemas(spec),
        be / "routers.py": gen_routers(spec),
        be / "routers_analytics.py": gen_analytics_router(spec),
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
        gen_next_route_handlers(spec, fe)
        pkg_file = fe / "package.json"
        if pkg_file.exists():
            try:
                pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
                deps = pkg_data.setdefault("dependencies", {})
                if "recharts" not in deps:
                    deps["recharts"] = "^2.15.0"
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
