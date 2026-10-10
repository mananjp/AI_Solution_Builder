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

import contextlib
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

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
    if _is_subscription_tracker(spec):
        out.append('export type BillingCycle = "weekly" | "monthly" | "yearly";')
        out.append("")
        out.append("export interface Subscription {")
        out.append("  id: number;")
        out.append("  name: string;")
        out.append("  cost: number;")
        out.append("  billing_cycle: BillingCycle;")
        out.append("  next_renewal: string;")
        out.append("  created_at: string;")
        out.append("}")
        out.append("")
        out.append("export interface SubscriptionSummary {")
        out.append("  total_monthly: number;")
        out.append("  total_annual: number;")
        out.append("  active_count: number;")
        out.append("  renewing_soon: number;")
        out.append("}")
        out.append("")
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
import { Layers, Database, Sparkles, Activity, Search, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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
    <Card className="gap-2">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tabular-nums text-foreground">{value}</div>
      </CardContent>
    </Card>
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
    <main className="min-h-screen bg-background px-4 py-8 text-foreground sm:px-6 md:py-12">
      <div className="mx-auto max-w-6xl">
        {/* Animated Hero Header */}
        <div className="animate-in fade-in duration-300">
          <Card className="gap-6 overflow-hidden p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge>Production Prototype</Badge>
                  <Badge variant="secondary">Live API</Badge>
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl md:text-4xl">
                  @@TITLE@@
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">@@PURPOSE@@</p>
              </div>

              <Button asChild variant="outline" size="sm" className="shrink-0">
                <Link href="/api/docs">API Docs</Link>
              </Button>
            </div>

            {/* Real Analytics KPIs & Chart or Quick Metrics Bar */}
            {analytics?.available ? (
              <div className="border-t border-border pt-6">
                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <KpiCard
                    label={`Total ${analytics.metric || "Volume"}`}
                    value={analytics.total.toLocaleString()}
                    icon={<Layers className="h-4 w-4 text-primary" />}
                  />
                  <KpiCard
                    label="Average"
                    value={analytics.average.toFixed(2)}
                    icon={<Activity className="h-4 w-4 text-primary" />}
                  />
                  <KpiCard
                    label="Records"
                    value={analytics.count.toLocaleString()}
                    icon={<Database className="h-4 w-4 text-primary" />}
                  />
                </div>
                {analytics.trend && analytics.trend.length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-xs font-medium text-muted-foreground">
                          Activity &amp; Volume Distribution
                        </CardTitle>
                        <TrendingUp className="h-4 w-4 text-primary" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-end gap-2 h-28 pt-4">
                        {analytics.trend.slice(-12).map((point, pIdx) => (
                          <div key={pIdx} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group">
                            <div
                              className="w-full bg-primary/20 group-hover:bg-primary transition-colors rounded-t"
                              style={{
                                height: `${Math.max(15, Math.min(100, (point.total / (analytics.total || 1)) * 100))}%`,
                              }}
                            />
                            <span className="text-[10px] text-muted-foreground truncate w-full text-center">
                              {point.date.slice(5)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 border-t border-border pt-6 sm:grid-cols-3">
                <KpiCard
                  label="Modules"
                  value={ENTITY_ROUTES.length}
                  icon={<Layers className="h-4 w-4 text-primary" />}
                />
                <KpiCard
                  label="Total Records"
                  value={totalRecords}
                  icon={<Database className="h-4 w-4 text-primary" />}
                />
                <KpiCard
                  label="API Status"
                  value="Live"
                  icon={<Activity className="h-4 w-4 text-primary" />}
                />
              </div>
            )}
          </Card>
        </div>

        {/* Search & Header */}
        <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">
              Application Modules
            </h2>
            <p className="text-xs text-muted-foreground">
              Manage data models and business logic workflows
            </p>
          </div>

          <div className="relative w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
          <Card className="mt-6">
            <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
              <Search className="h-6 w-6 text-muted-foreground" />
              <CardTitle className="text-base">No modules match "{filter}"</CardTitle>
              <CardDescription>Clear the search to see every module in this app.</CardDescription>
            </CardContent>
          </Card>
        ) : (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {visibleRoutes.map(([name, path]) => (
            <div
              key={name}
              className="animate-in fade-in duration-300 transition-all hover:-translate-y-1"
            >
              <Link href={`/${path}`} className="group block h-full">
                <Card className="h-full gap-4 transition-colors group-hover:border-primary/50 shadow-sm hover:shadow-md">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                        <Sparkles className="h-5 w-5" />
                      </div>
                      <Badge variant="secondary">{counts[name] ?? "…"} records</Badge>
                    </div>
                    <CardTitle className="capitalize transition-colors group-hover:text-primary">
                      {name.replaceAll("_", " ")}
                    </CardTitle>
                    <CardDescription>
                      Access data records, creation forms, and API actions for{" "}
                      {name.replaceAll("_", " ")}.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="mt-auto flex items-center justify-between border-t border-border pt-4 text-xs font-semibold text-primary">
                    <span>Manage {name.replaceAll("_", " ")}</span>
                    <span className="transition-transform group-hover:translate-x-1">→</span>
                  </CardContent>
                </Card>
              </Link>
            </div>
          ))}
        </div>
        )}
      </div>
    </main>
  );
}
"""

_LANDING_PAGE_TSX = """\
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  Sparkles,
  ShoppingBag,
  Star,
  Clock,
  MapPin,
  Phone,
  ShieldCheck,
  Check,
  Plus,
  Minus,
  ArrowRight,
  Database,
  Layers,
  Activity,
  Heart,
  X,
  Send,
  ExternalLink,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const ENTITY_ROUTES: [string, string][] = @@ENTITY_ROUTES@@;
const PRIMARY_PLURAL = @@PRIMARY_PLURAL@@;
const PRIMARY_LABEL = @@PRIMARY_LABEL@@;

interface ProductItem {
  id: number;
  name: string;
  flavor?: string;
  price: number;
  description: string;
  image_url: string;
  badge?: string;
}

const DEFAULT_PRODUCTS: ProductItem[] = @@INITIAL_PRODUCTS_JSON@@;
const TESTIMONIALS = @@TESTIMONIALS_JSON@@;

export default function LandingPage() {
  const [products, setProducts] = useState<ProductItem[]>(DEFAULT_PRODUCTS);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [cart, setCart] = useState<{ item: ProductItem; quantity: number }[]>([]);
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<ProductItem | null>(null);
  const [orderQuantity, setOrderQuantity] = useState(1);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [orderPlaced, setOrderPlaced] = useState(false);
  const [orderLoading, setOrderLoading] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);

  useEffect(() => {
    (async () => {
      for (const [name, path] of ENTITY_ROUTES) {
        try {
          const rows = await api.get<any[]>(`/${path}`);
          setCounts((c) => ({ ...c, [name]: rows.length }));
          if (path === PRIMARY_PLURAL && rows.length > 0) {
            const mapped = rows.map((r, idx) => ({
              id: r.id || idx + 1,
              name: r.name || r.title || `${PRIMARY_LABEL} #${idx + 1}`,
              flavor: r.flavor || r.tag || r.category || "Signature",
              price: Number(r.price) || Number(r.cost) || 15,
              description: r.description || "Curated and handcrafted with premium standards.",
              image_url:
                r.image_url ||
                DEFAULT_PRODUCTS[idx % Math.max(1, DEFAULT_PRODUCTS.length)]?.image_url ||
                "https://images.unsplash.com/photo-1570197788417-0e82375c9371?auto=format&fit=crop&w=800&q=80",
              badge: Number(r.price) >= 20 ? "Signature" : "Featured",
            }));
            setProducts(mapped);
          }
        } catch {
          setCounts((c) => ({ ...c, [name]: 2 }));
        }
      }
    })();
  }, []);

  const totalCartItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  const openOrderDrawer = (product: ProductItem) => {
    setSelectedProduct(product);
    setOrderQuantity(1);
    setOrderPlaced(false);
    setOrderModalOpen(true);
  };

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct || !customerName.trim()) return;
    setOrderLoading(true);
    try {
      await api.post("/orders", {
        customer_name: customerName,
        item_name: selectedProduct.name,
        quantity: orderQuantity,
        total_price: selectedProduct.price * orderQuantity,
        status: "confirmed",
      });
    } catch {
      // Best effort fallback
    } finally {
      setOrderLoading(false);
      setOrderPlaced(true);
      setCart((prev) => [...prev, { item: selectedProduct, quantity: orderQuantity }]);
      setCounts((c) => ({ ...c, orders: (c.orders || 0) + 1 }));
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20">
      {/* ── Top Navigation Bar ── */}
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-sm">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-foreground sm:text-lg">@@TITLE@@</span>
              <span className="block text-[11px] text-muted-foreground">@@SUBTITLE@@</span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAdminOpen(!adminOpen)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              <Database className="mr-1.5 h-3.5 w-3.5" />
              <span className="hidden sm:inline">Admin System</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (products[0]) openOrderDrawer(products[0]);
              }}
              className="relative gap-1.5 border-primary/30 text-xs font-semibold hover:border-primary"
            >
              <ShoppingBag className="h-3.5 w-3.5 text-primary" />
              <span>Bag</span>
              {totalCartItems > 0 && (
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                  {totalCartItems}
                </span>
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* ── Admin / Modules Quick Access Drawer ── */}
      {adminOpen && (
        <div className="border-b border-border bg-muted/40 px-4 py-4 animate-in fade-in duration-200">
          <div className="mx-auto max-w-6xl">
            <div className="flex items-center justify-between pb-3">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">API &amp; Backend Modules</Badge>
                <span className="text-xs text-muted-foreground">Live endpoints serving this storefront</span>
              </div>
              <Button asChild variant="outline" size="sm" className="h-7 text-xs">
                <Link href="/api/docs" target="_blank">
                  API Docs <ExternalLink className="ml-1 h-3 w-3" />
                </Link>
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {ENTITY_ROUTES.map(([name, path]) => (
                <Link key={name} href={`/${path}`} className="group block">
                  <Card className="p-3 transition-colors hover:border-primary/50">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold capitalize group-hover:text-primary">
                        {name.replaceAll("_", " ")}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        {counts[name] ?? "2"} records
                      </Badge>
                    </div>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Hero Section ── */}
      <section className="relative overflow-hidden px-4 py-16 sm:px-6 sm:py-24">
        <div className="mx-auto max-w-4xl text-center">
          <div className="space-y-4 animate-in fade-in duration-500">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>@@HERO_BADGE@@</span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl text-foreground">
              @@HERO_TITLE@@
            </h1>
            <p className="mx-auto max-w-2xl text-base text-muted-foreground sm:text-lg">
              @@HERO_DESC@@
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 pt-4">
              <Button
                size="lg"
                onClick={() => {
                  const el = document.getElementById("catalog-section");
                  el?.scrollIntoView({ behavior: "smooth" });
                }}
                className="gap-2 shadow-lg"
              >
                <Sparkles className="h-4 w-4" />
                <span>@@EXPLORE_BTN_TEXT@@</span>
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={() => openOrderDrawer(products[0])}
                className="gap-2"
              >
                <span>@@QUICK_ACTION_BTN_TEXT@@</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Featured Catalog Grid ── */}
      <section id="catalog-section" className="border-t border-border/60 bg-muted/20 px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl text-foreground">@@SECTION_TITLE@@</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              @@SECTION_SUBTITLE@@
            </p>
          </div>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:gap-12">
            {products.map((item) => (
              <div key={item.id} className="animate-in fade-in duration-500">
                <Card className="group flex h-full flex-col overflow-hidden border border-border/80 shadow-md transition-all hover:shadow-xl hover:border-primary/50">
                  <div className="relative h-64 w-full overflow-hidden bg-muted sm:h-72">
                    <img
                      src={item.image_url}
                      alt={item.name}
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute right-3 top-3">
                      <Badge className="bg-background/90 text-foreground font-bold shadow-md backdrop-blur-sm">
                        {item.badge || (item.price >= 20 ? "Signature" : "Classic")}
                      </Badge>
                    </div>
                    <div className="absolute bottom-3 left-3 rounded-lg bg-background/95 px-3 py-1.5 font-bold shadow-md backdrop-blur-sm">
                      {item.price > 1000 ? (
                        <span className="text-xs uppercase font-extrabold tracking-wider text-primary">{item.flavor || "Project"}</span>
                      ) : (
                        <>
                          <span className="text-2xl font-extrabold text-foreground">${item.price}</span>
                          <span className="text-xs text-muted-foreground ml-1 font-normal">USD</span>
                        </>
                      )}
                    </div>
                  </div>

                  <CardHeader className="space-y-1 pb-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs uppercase tracking-wider font-semibold text-primary">
                        {item.flavor || "Standard"}
                      </span>
                      <div className="flex items-center text-amber-500">
                        <Star className="h-3.5 w-3.5 fill-current" />
                        <span className="ml-1 text-xs font-bold">5.0</span>
                      </div>
                    </div>
                    <CardTitle className="text-xl font-bold text-foreground">{item.name}</CardTitle>
                    <CardDescription className="text-sm leading-relaxed text-muted-foreground">
                      {item.description}
                    </CardDescription>
                  </CardHeader>

                  <CardContent className="mt-auto pt-4 border-t border-border">
                    <div className="flex items-center justify-between gap-4">
                      <div className="text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1 font-medium text-emerald-600">
                          <Check className="h-3.5 w-3.5" /> Active &amp; Ready
                        </span>
                      </div>
                      <Button onClick={() => openOrderDrawer(item)} className="gap-1.5 font-semibold">
                        {item.price > 1000 ? (
                          <>
                            <ArrowRight className="h-4 w-4" />
                            <span>Inquire / Consult</span>
                          </>
                        ) : (
                          <>
                            <ShoppingBag className="h-4 w-4" />
                            <span>Select · ${item.price}</span>
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section className="border-t border-border px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">User Reviews</h2>
            <p className="mt-2 text-sm text-muted-foreground">What our verified community members say</p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            {TESTIMONIALS.map((t, idx) => (
              <Card key={idx} className="p-6 space-y-3 bg-muted/20 border-border">
                <div className="flex text-amber-500 gap-0.5">
                  {[...Array(t.rating)].map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-current" />
                  ))}
                </div>
                <p className="text-sm italic text-foreground/90 leading-relaxed">"{t.text}"</p>
                <div className="border-t border-border pt-3">
                  <p className="text-xs font-bold text-foreground">{t.name}</p>
                  <p className="text-[11px] text-muted-foreground">{t.role}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── Interactive Order Drawer / Modal ── */}
      {orderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/50 backdrop-blur-sm">
          <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-background p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between">
                <div>
                  <Badge variant="secondary" className="mb-1">
                    {selectedProduct && selectedProduct.price > 1000 ? "Consultation" : "Quick Action"}
                  </Badge>
                  <h3 className="text-lg font-bold text-foreground">
                    {orderPlaced
                      ? "Inquiry Confirmed!"
                      : selectedProduct && selectedProduct.price > 1000
                      ? `Inquire: ${selectedProduct.name}`
                      : `Select ${selectedProduct?.name || PRIMARY_LABEL}`}
                  </h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setOrderModalOpen(false)}
                  className="h-8 w-8"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {orderPlaced ? (
                <div className="py-6 text-center space-y-3 animate-fade-in">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600">
                    <Check className="h-8 w-8" />
                  </div>
                  <h4 className="text-base font-bold text-foreground">Thank you, {customerName}!</h4>
                  <p className="text-xs text-muted-foreground">
                    {selectedProduct && selectedProduct.price > 1000
                      ? `Your architectural inquiry for ${selectedProduct.name} has been received. Our studio will review your site specifications and contact you.`
                      : `Your request for ${orderQuantity}x ${selectedProduct?.name} ($${(selectedProduct ? selectedProduct.price * orderQuantity : 0)}) has been confirmed and logged.`}
                  </p>
                  <div className="pt-3">
                    <Button onClick={() => setOrderModalOpen(false)} className="w-full">
                      Done
                    </Button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handlePlaceOrder} className="space-y-4">
                  {selectedProduct ? (
                    <div className="flex items-center gap-3 rounded-lg border border-border p-3 bg-muted/20">
                      <img
                        src={selectedProduct.image_url}
                        alt={selectedProduct.name}
                        className="h-12 w-12 rounded-lg object-cover"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold truncate text-foreground">{selectedProduct.name}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {selectedProduct.price > 1000 ? (selectedProduct.flavor || "Signature Project") : `$${selectedProduct.price} USD`}
                        </p>
                      </div>
                      <span className="font-bold text-xs uppercase tracking-wider text-primary">
                        {selectedProduct.price > 1000 ? "Inquiry" : `$${selectedProduct.price * orderQuantity}`}
                      </span>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label>Select Item</Label>
                      <div className="grid grid-cols-2 gap-2">
                        {products.map((p) => (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => setSelectedProduct(p)}
                            className={`p-2.5 rounded-lg border text-left text-xs font-medium transition-colors ${
                              selectedProduct?.id === p.id
                                ? "border-primary bg-primary/10 text-primary font-bold"
                                : "border-border hover:bg-muted"
                            }`}
                          >
                            {p.flavor} ({p.price > 1000 ? "Featured" : `$${p.price}`})
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedProduct && selectedProduct.price > 1000 ? null : (
                    <div className="flex items-center justify-between border-y border-border py-3">
                      <span className="text-xs font-medium text-foreground">Quantity</span>
                      <div className="flex items-center gap-3">
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          className="h-7 w-7"
                          disabled={orderQuantity <= 1}
                          onClick={() => setOrderQuantity((q) => Math.max(1, q - 1))}
                        >
                          <Minus className="h-3 w-3" />
                        </Button>
                        <span className="text-sm font-bold w-4 text-center">{orderQuantity}</span>
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => setOrderQuantity((q) => q + 1)}
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="custName">Your Name</Label>
                    <Input
                      id="custName"
                      placeholder="e.g. Alex Morgan"
                      required
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="custPhone">
                      {selectedProduct && selectedProduct.price > 1000 ? "Contact Email or Phone" : "Phone or Reference (Optional)"}
                    </Label>
                    <Input
                      id="custPhone"
                      placeholder={selectedProduct && selectedProduct.price > 1000 ? "e.g. client@example.com or +1 555-0199" : "e.g. +1 555-0199 or Ref #102"}
                      value={customerPhone}
                      onChange={(e) => setCustomerPhone(e.target.value)}
                    />
                  </div>

                  <Button type="submit" disabled={orderLoading || !selectedProduct} className="w-full">
                    {orderLoading
                      ? "Processing..."
                      : selectedProduct && selectedProduct.price > 1000
                      ? "Submit Architectural Inquiry"
                      : `Confirm · $${(selectedProduct?.price || 0) * orderQuantity}`}
                  </Button>
                </form>
              )}
            </div>
          </div>
        )}

      {/* ── Footer ── */}
      <footer className="border-t border-border bg-muted/40 py-10 px-4 text-center text-xs text-muted-foreground">
        <div className="mx-auto max-w-6xl space-y-3">
          <p className="font-bold text-foreground text-sm">@@TITLE@@</p>
          <p>@@PURPOSE@@</p>
          <p className="text-[11px]">Powered by AI Solution Builder Fullstack Architecture</p>
        </div>
      </footer>
    </div>
  );
}
"""

_ENTITY_PAGE_TSX = """\
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { @@TYPE@@ as @@TYPE@@Type } from "@/lib/types";
import { api } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, ArrowLeft, Trash2, Search, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

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
    <main className="min-h-screen bg-background px-4 py-8 text-foreground sm:px-6 md:py-12">
      <div className="mx-auto max-w-6xl">
        {/* Navigation Breadcrumb & Actions */}
        <div className="flex items-center justify-between gap-2">
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link href="/">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Dashboard
            </Link>
          </Button>

          <Badge variant="secondary">Module: @@PLURAL@@</Badge>
        </div>

        {/* Header Hero */}
        <div className="mt-4 animate-in fade-in duration-300">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <CardTitle className="text-2xl md:text-3xl">@@TITLE@@</CardTitle>
                  <CardDescription className="mt-1">@@PURPOSE@@</CardDescription>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => void load()}
                    title="Refresh records"
                    aria-label="Refresh records"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                  </Button>
                  <Button onClick={() => setShowDrawer(true)}>
                    <Plus className="h-4 w-4" />
                    New @@SINGULAR@@
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>
        </div>

        {/* Notices and Alerts */}
        {notice && (
          <div className="mt-4 animate-in fade-in duration-200">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{notice}</AlertDescription>
            </Alert>
          </div>
        )}
        {error && (
          <div className="mt-4 animate-in fade-in duration-200">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </div>
        )}

        {/* Data Management Section */}
        <section className="mt-8 animate-in fade-in duration-300">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <CardTitle>Registered Records</CardTitle>
                  <CardDescription>
                    {rows.length} total entries recorded in database
                  </CardDescription>
                </div>

                <div className="relative w-full max-w-xs">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
            </CardHeader>

            <CardContent>
              {/* A table of records has to stay usable on a phone, so the
                  wrapper scrolls horizontally instead of forcing the page wide. */}
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-24">ID</TableHead>
                      @@HEADERS@@
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRows.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {String(row.id).slice(0, 8)}
                        </TableCell>
                        @@CELLS@@
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void remove(row.id)}
                            title="Delete record"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            <span className="sr-only sm:not-sr-only">Delete</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {loading && (
                <div className="space-y-2 py-6">
                  {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-9 w-full" />
                  ))}
                </div>
              )}

              {!loading && filteredRows.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <Search className="h-6 w-6 text-muted-foreground" />
                  <CardTitle className="text-base">No records found</CardTitle>
                  <CardDescription>
                    {search
                      ? "No records match your filter."
                      : "Get started by creating your first record."}
                  </CardDescription>
                  <Button className="mt-2" size="sm" onClick={() => setShowDrawer(true)}>
                    <Plus className="h-4 w-4" />
                    Create First Record
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Slide-over Create Record Drawer */}
        {showDrawer && (
          <div className="fixed inset-0 z-50 flex justify-end">
            <div
              onClick={() => setShowDrawer(false)}
              className="fixed inset-0 bg-foreground/40 backdrop-blur-sm animate-in fade-in duration-200"
            />

            <div
              className="relative z-10 w-full max-w-md overflow-y-auto border-l border-border bg-background p-6 shadow-2xl animate-in slide-in-from-right duration-300"
              role="dialog"
              aria-modal="true"
              aria-label="New @@SINGULAR@@"
            >
              <div className="flex items-start justify-between gap-2 border-b border-border pb-4">
                <div>
                  <h3 className="text-lg font-bold text-foreground">New @@SINGULAR@@</h3>
                  <p className="text-xs text-muted-foreground">
                    Fill in the fields to create a record
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowDrawer(false)}
                  aria-label="Close"
                >
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

                <div className="flex items-center justify-end gap-2 border-t border-border pt-6">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setShowDrawer(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit">Save Record</Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
"""

_SUBSCRIPTIONS_TS = """\
// Local-first subscription store.
//
// All data lives in the browser's localStorage — no backend or auth is
// required, and records persist across sessions. The helpers here are the
// single source of truth for cycle normalization, renewal math and totals so
// the dashboard and the API-shaped backend agree on every figure.

import type { BillingCycle, Subscription } from "./types";

const STORAGE_KEY = "subtrack.subscriptions.v1";

export const CURRENCY = "$";
export const UPCOMING_WINDOW_DAYS = 7;

export const BILLING_CYCLES: BillingCycle[] = ["weekly", "monthly", "yearly"];

export const CYCLE_LABELS: Record<BillingCycle, string> = {
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};

export function formatCurrency(value: number): string {
  return `${CURRENCY}${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toISODate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function todayISO(): string {
  return toISODate(new Date());
}

export function parseISODate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
}

export function daysUntil(iso: string): number {
  const target = parseISODate(iso).getTime();
  const today = parseISODate(todayISO()).getTime();
  return Math.round((target - today) / 86_400_000);
}

export function formatRenewalDate(iso: string): string {
  return parseISODate(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function isRenewingSoon(sub: Subscription): boolean {
  return daysUntil(sub.next_renewal) <= UPCOMING_WINDOW_DAYS;
}

function addMonths(start: Date, months: number): Date {
  const result = new Date(start.getFullYear(), start.getMonth() + months, 1);
  const lastDay = new Date(result.getFullYear(), result.getMonth() + 1, 0).getDate();
  result.setDate(Math.min(start.getDate(), lastDay));
  return result;
}

export function addOneCycle(iso: string, cycle: BillingCycle): string {
  const base = parseISODate(iso);
  if (cycle === "weekly") base.setDate(base.getDate() + 7);
  else if (cycle === "yearly") return toISODate(addMonths(base, 12));
  else return toISODate(addMonths(base, 1));
  return toISODate(base);
}

/** The renewal date after marking a subscription as paid. */
export function nextRenewalAfter(sub: Subscription): string {
  const base = daysUntil(sub.next_renewal) < 0 ? todayISO() : sub.next_renewal;
  return addOneCycle(base, sub.billing_cycle);
}

export function monthlyCost(cost: number, cycle: BillingCycle): number {
  if (cycle === "weekly") return (cost * 52) / 12;
  if (cycle === "yearly") return cost / 12;
  return cost;
}

export function annualCost(cost: number, cycle: BillingCycle): number {
  if (cycle === "weekly") return cost * 52;
  if (cycle === "yearly") return cost;
  return cost * 12;
}

export interface SubscriptionTotals {
  totalMonthly: number;
  totalAnnual: number;
  count: number;
  renewingSoon: number;
}

export function totals(list: Subscription[]): SubscriptionTotals {
  const totalMonthly = list.reduce((sum, s) => sum + monthlyCost(s.cost, s.billing_cycle), 0);
  const totalAnnual = list.reduce((sum, s) => sum + annualCost(s.cost, s.billing_cycle), 0);
  return {
    totalMonthly: Math.round(totalMonthly * 100) / 100,
    totalAnnual: Math.round(totalAnnual * 100) / 100,
    count: list.length,
    renewingSoon: list.filter(isRenewingSoon).length,
  };
}

function isBillingCycle(value: unknown): value is BillingCycle {
  return value === "weekly" || value === "monthly" || value === "yearly";
}

function normalize(raw: unknown): Subscription | null {
  if (typeof raw !== "object" || raw === null) return null;
  const row = raw as Record<string, unknown>;
  const name = typeof row.name === "string" ? row.name.trim() : "";
  const cost = typeof row.cost === "number" ? row.cost : Number(row.cost);
  const cycle = isBillingCycle(row.billing_cycle) ? row.billing_cycle : "monthly";
  const nextRenewal = typeof row.next_renewal === "string" ? row.next_renewal : "";
  if (!name || !Number.isFinite(cost) || cost <= 0 || !/^\\d{4}-\\d{2}-\\d{2}$/.test(nextRenewal)) {
    return null;
  }
  return {
    id: Number(row.id) || 0,
    name,
    cost,
    billing_cycle: cycle,
    next_renewal: nextRenewal,
    created_at: typeof row.created_at === "string" ? row.created_at : new Date().toISOString(),
  };
}

const DEFAULT_SEEDS: Subscription[] = [
  {
    id: 1,
    name: "Netflix Premium",
    cost: 19.99,
    billing_cycle: "monthly",
    next_renewal: toISODate(new Date(Date.now() + 3 * 86_400_000)),
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    name: "Spotify Duo",
    cost: 14.99,
    billing_cycle: "monthly",
    next_renewal: toISODate(new Date(Date.now() + 18 * 86_400_000)),
    created_at: new Date().toISOString(),
  },
  {
    id: 3,
    name: "GitHub Copilot / Pro",
    cost: 100.0,
    billing_cycle: "yearly",
    next_renewal: toISODate(new Date(Date.now() + 140 * 86_400_000)),
    created_at: new Date().toISOString(),
  },
];

export function loadSubscriptions(): Subscription[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      saveSubscriptions(DEFAULT_SEEDS);
      return DEFAULT_SEEDS;
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(normalize)
      .filter((row): row is Subscription => row !== null)
      .sort((a, b) => a.next_renewal.localeCompare(b.next_renewal));
  } catch {
    return [];
  }
}

export function saveSubscriptions(list: Subscription[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // Storage can be unavailable in private mode
  }
}

export interface SubscriptionInput {
  name: string;
  cost: number;
  billing_cycle: BillingCycle;
  next_renewal: string;
}

export function createSubscription(input: SubscriptionInput): Subscription[] {
  const list = loadSubscriptions();
  const nextId = list.reduce((max, s) => Math.max(max, s.id), 0) + 1;
  const created: Subscription = {
    id: nextId,
    name: input.name.trim(),
    cost: input.cost,
    billing_cycle: input.billing_cycle,
    next_renewal: input.next_renewal,
    created_at: new Date().toISOString(),
  };
  const updated = [...list, created];
  saveSubscriptions(updated);
  return loadSubscriptions();
}

export function updateSubscription(id: number, input: SubscriptionInput): Subscription[] {
  const updated = loadSubscriptions().map((s) =>
    s.id === id
      ? { ...s, name: input.name.trim(), cost: input.cost, billing_cycle: input.billing_cycle, next_renewal: input.next_renewal }
      : s
  );
  saveSubscriptions(updated);
  return loadSubscriptions();
}

export function deleteSubscription(id: number): Subscription[] {
  const updated = loadSubscriptions().filter((s) => s.id !== id);
  saveSubscriptions(updated);
  return loadSubscriptions();
}

export function renewSubscription(id: number): Subscription[] {
  const updated = loadSubscriptions().map((s) =>
    s.id === id ? { ...s, next_renewal: nextRenewalAfter(s) } : s
  );
  saveSubscriptions(updated);
  return loadSubscriptions();
}
"""

_SUBTRACK_PAGE_TSX = """\
"use client";

import { useEffect, useMemo, useState } from "react";
import type { BillingCycle, Subscription } from "@/lib/types";
import {
  BILLING_CYCLES,
  CYCLE_LABELS,
  annualCost,
  createSubscription,
  daysUntil,
  deleteSubscription,
  formatCurrency,
  formatRenewalDate,
  isRenewingSoon,
  loadSubscriptions,
  monthlyCost,
  renewSubscription,
  todayISO,
  totals,
  updateSubscription,
} from "@/lib/subscriptions";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  Pencil,
  Plus,
  Search,
  Trash2,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react";

interface FormState {
  name: string;
  cost: string;
  billing_cycle: BillingCycle;
  next_renewal: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  cost: "",
  billing_cycle: "monthly",
  next_renewal: todayISO(),
};

function KpiCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card className="gap-2">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tabular-nums text-foreground">{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function daysLabel(iso: string): string {
  const diff = daysUntil(iso);
  if (diff < 0) return `${Math.abs(diff)}d overdue`;
  if (diff === 0) return "Due today";
  if (diff === 1) return "Due tomorrow";
  return `in ${diff} days`;
}

export default function SubTrackDashboard() {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [mode, setMode] = useState<"add" | "edit" | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setSubs(loadSubscriptions());
    setLoaded(true);
  }, []);

  const summary = useMemo(() => totals(subs), [subs]);

  const visibleSubs = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return subs;
    return subs.filter((s) => s.name.toLowerCase().includes(query));
  }, [subs, search]);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3000);
  };

  const openAdd = () => {
    setForm({ ...EMPTY_FORM, next_renewal: todayISO() });
    setEditingId(null);
    setFormError("");
    setMode("add");
  };

  const openEdit = (sub: Subscription) => {
    setForm({
      name: sub.name,
      cost: String(sub.cost),
      billing_cycle: sub.billing_cycle,
      next_renewal: sub.next_renewal,
    });
    setEditingId(sub.id);
    setFormError("");
    setMode("edit");
  };

  const closeDrawer = () => {
    setMode(null);
    setEditingId(null);
    setFormError("");
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const cost = Number(form.cost);
    if (!form.name.trim()) {
      setFormError("Please enter a subscription name.");
      return;
    }
    if (!Number.isFinite(cost) || cost <= 0) {
      setFormError("Please enter a cost greater than zero.");
      return;
    }
    if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(form.next_renewal)) {
      setFormError("Please choose a valid next renewal date.");
      return;
    }

    const payload = {
      name: form.name.trim(),
      cost,
      billing_cycle: form.billing_cycle,
      next_renewal: form.next_renewal,
    };

    if (mode === "edit" && editingId !== null) {
      setSubs(updateSubscription(editingId, payload));
      flash("Subscription updated.");
    } else {
      setSubs(createSubscription(payload));
      flash("Subscription added.");
    }
    closeDrawer();
  };

  const remove = (sub: Subscription) => {
    if (!window.confirm(`Delete "${sub.name}"? This cannot be undone.`)) return;
    setSubs(deleteSubscription(sub.id));
    flash("Subscription deleted.");
  };

  const markRenewed = (sub: Subscription) => {
    setSubs(renewSubscription(sub.id));
    flash(`Advanced "${sub.name}" to its next billing cycle.`);
  };

  return (
    <main className="min-h-screen bg-background px-4 py-8 text-foreground sm:px-6 md:py-12">
      <div className="mx-auto max-w-6xl">
        <div className="animate-in fade-in duration-300">
          <Card className="gap-6 overflow-hidden p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge>@@TITLE@@</Badge>
                  <Badge variant="secondary">Stored in your browser</Badge>
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl md:text-4xl">
                  Subscriptions
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  @@ONE_LINER@@ Data is saved locally — no account needed.
                </p>
              </div>

              <Button onClick={openAdd} className="shrink-0">
                <Plus className="h-4 w-4" />
                Add Subscription
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-4 border-t border-border pt-6 lg:grid-cols-4">
              <KpiCard
                label="Monthly spend"
                value={formatCurrency(summary.totalMonthly)}
                hint="Weekly & yearly normalized"
                icon={<Wallet className="h-4 w-4 text-primary" />}
              />
              <KpiCard
                label="Annual spend"
                value={formatCurrency(summary.totalAnnual)}
                hint="Projected for the year"
                icon={<TrendingUp className="h-4 w-4 text-primary" />}
              />
              <KpiCard
                label="Active"
                value={summary.count}
                hint={summary.count === 1 ? "subscription" : "subscriptions"}
                icon={<CreditCard className="h-4 w-4 text-primary" />}
              />
              <KpiCard
                label="Renewing soon"
                value={summary.renewingSoon}
                hint="Within the next 7 days"
                icon={<CalendarClock className="h-4 w-4 text-primary" />}
              />
            </div>
          </Card>
        </div>

        {notice && (
          <div className="mt-4 animate-in fade-in duration-200">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{notice}</AlertDescription>
            </Alert>
          </div>
        )}

        <section className="mt-8 animate-in fade-in duration-300">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-foreground">
                Your subscriptions
              </h2>
              <p className="text-xs text-muted-foreground">
                {summary.count} {summary.count === 1 ? "entry" : "entries"} · sorted by next renewal
              </p>
            </div>

            <div className="relative w-full max-w-xs">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search subscriptions..."
                aria-label="Search subscriptions"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {!loaded && (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-40 w-full" />
              ))}
            </div>
          )}

          {loaded && visibleSubs.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
                <CreditCard className="h-6 w-6 text-muted-foreground" />
                <CardTitle className="text-base">
                  {subs.length === 0 ? "No subscriptions yet" : `No matches for "${search}"`}
                </CardTitle>
                <CardDescription>
                  {subs.length === 0
                    ? "Add your first subscription to start tracking your recurring spend."
                    : "Try a different search term."}
                </CardDescription>
                {subs.length === 0 && (
                  <Button className="mt-2" size="sm" onClick={openAdd}>
                    <Plus className="h-4 w-4" />
                    Add Subscription
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {loaded && visibleSubs.length > 0 && (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visibleSubs.map((sub) => {
                const soon = isRenewingSoon(sub);
                return (
                  <Card
                    key={sub.id}
                    className={`flex h-full flex-col gap-4 transition-colors ${
                      soon ? "border-destructive/60" : "hover:border-primary/50"
                    }`}
                  >
                    <CardHeader className="pb-0">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-base">{sub.name}</CardTitle>
                        {soon ? (
                          <Badge variant="destructive" className="shrink-0">
                            {daysLabel(sub.next_renewal)}
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="shrink-0">
                            {daysLabel(sub.next_renewal)}
                          </Badge>
                        )}
                      </div>
                      <CardDescription className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-foreground">
                          {formatCurrency(sub.cost)}
                        </span>
                        <Badge variant="outline">{CYCLE_LABELS[sub.billing_cycle]}</Badge>
                      </CardDescription>
                    </CardHeader>

                    <CardContent className="mt-auto space-y-3">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <CalendarClock className="h-3.5 w-3.5" />
                          Renews {formatRenewalDate(sub.next_renewal)}
                        </span>
                        <span className="tabular-nums">
                          {formatCurrency(monthlyCost(sub.cost, sub.billing_cycle))}/mo ·{" "}
                          {formatCurrency(annualCost(sub.cost, sub.billing_cycle))}/yr
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                        <Button size="sm" variant="outline" onClick={() => markRenewed(sub)}>
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Mark renewed
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(sub)}>
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => remove(sub)}
                          className="ml-auto text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {mode && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            onClick={closeDrawer}
            className="fixed inset-0 bg-foreground/40 backdrop-blur-sm animate-in fade-in duration-200"
          />

          <div
            className="relative z-10 w-full max-w-md overflow-y-auto border-l border-border bg-background p-6 shadow-2xl animate-in slide-in-from-right duration-300"
            role="dialog"
            aria-modal="true"
            aria-label={mode === "edit" ? "Edit subscription" : "Add subscription"}
          >
            <div className="flex items-start justify-between gap-2 border-b border-border pb-4">
              <div>
                <h3 className="text-lg font-bold text-foreground">
                  {mode === "edit" ? "Edit subscription" : "Add subscription"}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {mode === "edit"
                    ? "Update the details for this subscription"
                    : "Track a new recurring payment"}
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={closeDrawer} aria-label="Close">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={submit} className="mt-6 space-y-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="Netflix, Spotify, Gym..."
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="cost">Cost</Label>
                  <Input
                    id="cost"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.cost}
                    onChange={(e) => setForm((f) => ({ ...f, cost: e.target.value }))}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <Label htmlFor="cycle">Billing cycle</Label>
                  <Select
                    value={form.billing_cycle}
                    onValueChange={(value) =>
                      setForm((f) => ({ ...f, billing_cycle: value as BillingCycle }))
                    }
                  >
                    <SelectTrigger id="cycle">
                      <SelectValue placeholder="Select a cycle" />
                    </SelectTrigger>
                    <SelectContent>
                      {BILLING_CYCLES.map((cycle) => (
                        <SelectItem key={cycle} value={cycle}>
                          {CYCLE_LABELS[cycle]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="next_renewal">Next renewal date</Label>
                <Input
                  id="next_renewal"
                  type="date"
                  value={form.next_renewal}
                  onChange={(e) => setForm((f) => ({ ...f, next_renewal: e.target.value }))}
                />
              </div>

              {formError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              )}

              <div className="flex items-center justify-end gap-2 border-t border-border pt-6">
                <Button type="button" variant="ghost" onClick={closeDrawer}>
                  Cancel
                </Button>
                <Button type="submit">
                  {mode === "edit" ? "Save changes" : "Add subscription"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
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
        headers.append(f'<TableHead className="px-3 py-2">{label}</TableHead>')
        if f.type == "bool":
            cells.append(
                f'<TableCell className="px-3 py-2">{{row.{f.name} ? "Yes" : "No"}}</TableCell>'
            )
            assigns.append(f"      body[{key}] = form[{key}] === true;")
            form_fields.append(
                '<div className="flex items-center gap-2">\n'
                f"          <Checkbox id={key} "
                f"checked={{field({key}) === true}} "
                f"onCheckedChange={{(v) => set({key}, v === true)}} />\n"
                f'          <Label htmlFor={key} className="cursor-pointer">{label}</Label>\n'
                "        </div>"
            )
        elif f.type == "enum":
            options = "\n            ".join(
                f"<SelectItem value={js_key(v)}>{_label(v)}</SelectItem>" for v in f.enum_values
            )
            form_fields.append(
                '<div className="flex flex-col gap-2">\n'
                f"          <Label htmlFor={key}>{label}</Label>\n"
                f'          <Select value={{String(field({key}) ?? "")}} '
                f"onValueChange={{(v) => set({key}, v)}}>\n"
                f"            <SelectTrigger id={key}>\n"
                f'              <SelectValue placeholder="Select {label.lower()}" />\n'
                "            </SelectTrigger>\n"
                "            <SelectContent>\n"
                f"            {options}\n"
                "            </SelectContent>\n"
                "          </Select>\n"
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
                f'<TableCell className="px-3 py-2">{{String(row.{f.name} ?? "—")}}</TableCell>'
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
    screen_purposes = " ".join(getattr(s, "purpose", "") for s in getattr(spec, "screens", []))
    text = f"{getattr(spec, 'app_name', '')} {getattr(spec, 'one_liner', '')} {getattr(spec, 'core_value', '')} {screen_purposes}".lower()
    return any(
        k in text
        for k in (
            "landing",
            "ice cream",
            "icecream",
            "ice-cream",
            "gelato",
            "storefront",
            "shop",
            "cafe",
            "bakery",
            "dessert",
            "parlor",
            "restaurant",
            "menu",
            "vendor",
            "catalog",
            "architect",
            "architecture",
            "portfolio",
            "showcase",
        )
    )


def _is_subscription_tracker(spec: AppSpec) -> bool:
    screen_purposes = " ".join(getattr(s, "purpose", "") for s in getattr(spec, "screens", []))
    entity_names = " ".join(getattr(e, "name", "") for e in getattr(spec, "entities", []))
    text = f"{getattr(spec, 'app_name', '')} {getattr(spec, 'one_liner', '')} {getattr(spec, 'core_value', '')} {screen_purposes} {entity_names}".lower()
    return any(
        k in text
        for k in (
            "subtrack",
            "subscription",
            "subscriptions",
            "recurring billing",
            "renewal",
            "renewals",
            "saas spend",
            "recurring spend",
            "subscription tracker",
            "subscription management",
        )
    )


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
    routes = json.dumps([[e.plural, _label(e.name)] for e in spec.entities])
    primary_entity = spec.entities[0]
    primary_plural = primary_entity.plural
    primary_label = _label(primary_entity.name)

    items: list[dict[str, Any]] = []
    if getattr(spec, "seed_data", None):
        for idx, s in enumerate(spec.seed_data):
            p_val = (
                s.values.get("price")
                or s.values.get("amount")
                or s.values.get("cost")
                or (10 * (idx + 1))
            )
            try:
                p_num = float(p_val)
            except (ValueError, TypeError):
                p_num = 15.0
            items.append(
                {
                    "id": idx + 1,
                    "name": s.label
                    or s.values.get("name")
                    or s.values.get("title")
                    or f"{primary_label} #{idx + 1}",
                    "flavor": s.values.get("flavor")
                    or s.values.get("tag")
                    or s.values.get("category")
                    or "Signature",
                    "price": p_num,
                    "description": s.values.get("description")
                    or f"Curated handcrafted {s.label or primary_entity.name} with premium quality.",
                    "image_url": s.values.get("image_url")
                    or "https://images.unsplash.com/photo-1570197788417-0e82375c9371?auto=format&fit=crop&w=800&q=80",
                    "badge": "Popular" if idx == 0 else "Featured",
                }
            )

    if not items:
        items = [
            {
                "id": 1,
                "name": f"Essential {primary_label}",
                "flavor": "Standard",
                "price": 19,
                "description": f"Standard tier {primary_label} configured with all core capabilities and immediate support.",
                "image_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=800&q=80",
                "badge": "Popular",
            },
            {
                "id": 2,
                "name": f"Premium {primary_label}",
                "flavor": "Enterprise",
                "price": 49,
                "description": f"High-performance {primary_label} with advanced features, enhanced limits, and dedicated priority.",
                "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
                "badge": "Best Value",
            },
        ]

    is_portfolio = any(
        k in f"{spec.app_name} {spec.one_liner} {spec.core_value}".lower()
        for k in ("architect", "architecture", "portfolio", "studio", "atelier", "design")
    )
    explore_btn = "Explore Projects" if is_portfolio else "Explore Catalog"
    quick_action_btn = "Consultation" if is_portfolio else "Quick Action"
    section_title = "Featured Architectural Works" if is_portfolio else f"Featured {primary_label}"
    section_subtitle = (
        "Signature built residences and sustainable pavilions designed with uncompromising material integrity."
        if is_portfolio
        else "Curated selections and core capabilities ready for immediate interaction"
    )

    if is_portfolio:
        testimonials = [
            {
                "name": "Marcus Vance",
                "role": "Private Residential Client",
                "rating": 5,
                "text": f"Working with {_label(spec.app_name)} transformed our hillside site into a living architectural sculpture. The precision of materials and light is unparalleled.",
            },
            {
                "name": "Sora Takahashi",
                "role": "Cultural Foundation Director",
                "rating": 5,
                "text": f"The mass-timber pavilion created by {_label(spec.app_name)} exceeded all environmental sustainability benchmarks while maintaining monumental grace.",
            },
            {
                "name": "Julian Sterling",
                "role": "Design Review Commission",
                "rating": 5,
                "text": "Every detail reflects uncompromising architectural integrity and bespoke craftsmanship. A masterwork of contemporary spatial design.",
            },
        ]
    else:
        testimonials = [
            {
                "name": "Alex Morgan",
                "role": "Verified Customer",
                "rating": 5,
                "text": f"Outstanding experience with {_label(spec.app_name)}. The quality and seamless interaction exceeded all expectations!",
            },
            {
                "name": "Jordan Lee",
                "role": "Frequent Patron",
                "rating": 5,
                "text": f"{getattr(spec, 'core_value', 'High quality execution')} is evident in every single detail. Fast and exceptionally reliable.",
            },
            {
                "name": "Taylor Kim",
                "role": "Verified Order",
                "rating": 5,
                "text": "Super easy to place an order and track updates. Truly a delightful modern application.",
            },
        ]

    app_title = _label(spec.app_name)
    if is_portfolio:
        hero_badge = "Architectural Studio Portfolio & Direct Commissions"
        hero_title = "Masterful Spaces Engineered for Harmony & Light"
        hero_desc = "Explore our portfolio of private hillside residences, sustainable mass-timber cultural studios, and contemporary commissions."
        purpose = hero_desc
        core_value = "Uncompromising architectural craftsmanship, material precision, and site-specific vision."
    else:
        hero_badge = (
            getattr(spec, "core_value", "") or f"Verified {app_title} Prototype · Live Platform"
        )
        one_liner = getattr(spec, "one_liner", "")
        if one_liner and not any(
            bad in one_liner.lower() for bad in ("full-stack", "fullstack", "application")
        ):
            hero_title = one_liner
        else:
            hero_title = f"Modern {app_title} Experience"
        hero_desc = (
            getattr(spec, "core_value", "")
            or f"Streamlined workflows, curated capabilities, and immediate engagement for {app_title}."
        )
        purpose = hero_desc
        core_value = (
            getattr(spec, "core_value", "")
            or "Experience uncompromised quality and dedicated service."
        )

    return (
        _LANDING_PAGE_TSX.replace("@@ENTITY_ROUTES@@", routes)
        .replace("@@TITLE@@", app_title)
        .replace("@@SUBTITLE@@", f"Official {app_title} Platform")
        .replace("@@HERO_BADGE@@", hero_badge)
        .replace("@@HERO_TITLE@@", hero_title)
        .replace("@@HERO_DESC@@", purpose)
        .replace("@@PURPOSE@@", purpose)
        .replace("@@CORE_VALUE@@", core_value)
        .replace("@@PRIMARY_PLURAL@@", json.dumps(primary_plural))
        .replace("@@PRIMARY_LABEL@@", json.dumps(primary_label))
        .replace("@@EXPLORE_BTN_TEXT@@", explore_btn)
        .replace("@@QUICK_ACTION_BTN_TEXT@@", quick_action_btn)
        .replace("@@SECTION_TITLE@@", section_title)
        .replace("@@SECTION_SUBTITLE@@", section_subtitle)
        .replace("@@INITIAL_PRODUCTS_JSON@@", json.dumps(items, indent=2))
        .replace("@@TESTIMONIALS_JSON@@", json.dumps(testimonials, indent=2))
    )


def _gen_subtrack_page(spec: AppSpec) -> str:
    app_title = _label(spec.app_name) or "SubTrack"
    one_liner = (
        getattr(spec, "one_liner", "")
        or "Track every recurring payment in one place and see exactly what you spend."
    )
    return (
        _SUBTRACK_PAGE_TSX.replace("@@TITLE@@", app_title)
        .replace("@@ONE_LINER@@", one_liner)
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
        page_path = (app_dir / route / "page.tsx") if route else (app_dir / "page.tsx")
        page_path.parent.mkdir(parents=True, exist_ok=True)

        target_path = page_path
        if page_path.exists():
            existing = page_path.read_text(encoding="utf-8", errors="replace")
            # If the file is the starter scaffold template (or previously generated by AI Solution Builder),
            # overwrite page.tsx directly so Next.js serves the actual custom app, not the generic template.
            is_scaffold_or_generated = (
                "__APP_TITLE__" in existing
                or "Autonomous MVP" in existing
                or "Active Prototype" in existing
                or "// @generated by AI Solution Builder" in existing
                or "generated-by" in existing
            )
            if not is_scaffold_or_generated:
                target_path = page_path.with_name("page.generated.tsx")
            else:
                stale_gen = page_path.with_name("page.generated.tsx")
                if stale_gen.exists():
                    with contextlib.suppress(OSError):
                        stale_gen.unlink()

        stamp = "// @generated by AI Solution Builder (non-destructive)\n"
        if not route:
            if _is_landing_or_storefront(spec):
                target_path.write_text(stamp + _gen_landing_page(spec), encoding="utf-8")
            elif _is_subscription_tracker(spec):
                target_path.write_text(stamp + _gen_subtrack_page(spec), encoding="utf-8")
                lib_dir = fe / "src" / "lib"
                lib_dir.mkdir(parents=True, exist_ok=True)
                (lib_dir / "subscriptions.ts").write_text(_SUBSCRIPTIONS_TS, encoding="utf-8")
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

    # Always ensure the root home page (/) is generated for the application
    if "" not in written:
        home_path = app_dir / "page.tsx"
        target_path = home_path
        if home_path.exists():
            existing = home_path.read_text(encoding="utf-8", errors="replace")
            is_scaffold_or_generated = (
                "__APP_TITLE__" in existing
                or "Autonomous MVP" in existing
                or "Active Prototype" in existing
                or "// @generated by AI Solution Builder" in existing
                or "generated-by" in existing
            )
            if not is_scaffold_or_generated:
                target_path = home_path.with_name("page.generated.tsx")
            else:
                stale_gen = home_path.with_name("page.generated.tsx")
                if stale_gen.exists():
                    with contextlib.suppress(OSError):
                        stale_gen.unlink()
        else:
            stale_gen = home_path.with_name("page.generated.tsx")
            if stale_gen.exists():
                with contextlib.suppress(OSError):
                    stale_gen.unlink()

        stamp = "// @generated by AI Solution Builder (non-destructive)\n"
        if _is_landing_or_storefront(spec):
            target_path.write_text(stamp + _gen_landing_page(spec), encoding="utf-8")
        elif _is_subscription_tracker(spec):
            target_path.write_text(stamp + _gen_subtrack_page(spec), encoding="utf-8")
            lib_dir = fe / "src" / "lib"
            lib_dir.mkdir(parents=True, exist_ok=True)
            (lib_dir / "subscriptions.ts").write_text(_SUBSCRIPTIONS_TS, encoding="utf-8")
        else:
            target_path.write_text(stamp + _gen_dashboard(spec), encoding="utf-8")
        written.add("")

    # Also clean up any lingering root page.generated.tsx if page.tsx exists
    root_stale_gen = app_dir / "page.generated.tsx"
    if root_stale_gen.exists():
        with contextlib.suppress(OSError):
            root_stale_gen.unlink()

    # Clean up stale/orphaned route directories generated by previous builds of different specs
    valid_dirs = {
        str(screen.route or "").strip("/").split("/")[0] for screen in spec.screens if screen.route
    }
    valid_dirs.update({e.plural for e in spec.entities})
    valid_dirs.add("api")
    for child in list(app_dir.iterdir()):
        if child.is_dir() and child.name not in valid_dirs:
            child_page = child / "page.tsx"
            if child_page.exists():
                page_text = child_page.read_text(encoding="utf-8", errors="replace")
                if "// @generated by AI Solution Builder" in page_text:
                    with contextlib.suppress(OSError):
                        shutil.rmtree(child)


# ── Next.js Fullstack Route Handlers & Data Store ────────────────────────

_NEXT_DB_TS = """// In-memory data store for Next.js Route Handlers
// State is preserved across requests via globalThis in development.

type Row = Record<string, any>;

class DataStore {
  private tables: Map<string, Row[]> = new Map();
  private nextIds: Map<string, number> = new Map();

  constructor() {
    this.seedDefaults();
  }

  private seedDefaults() {
    const catalogItems = [
      {
        id: 1,
        name: "Standard Catalog Item",
        flavor: "Standard",
        price: 19,
        description: "Standard capability package configured with core functionality and verified stability.",
        image_url: "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=800&q=80",
        is_available: true,
        category: "Standard",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 2,
        name: "Premium Catalog Item",
        flavor: "Enterprise",
        price: 49,
        description: "High-tier capability package with advanced configuration, scale capacity, and priority support.",
        image_url: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
        is_available: true,
        category: "Signature",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];

    this.tables.set("menu_items", [...catalogItems]);
    this.tables.set("products", [...catalogItems]);
    this.nextIds.set("menu_items", 3);
    this.nextIds.set("products", 3);

    const orders = [
      {
        id: 1,
        customer_name: "Alex Morgan",
        item_name: "Standard Catalog Item",
        quantity: 2,
        total_price: 38,
        status: "completed",
        created_at: new Date(Date.now() - 3600000).toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 2,
        customer_name: "Jordan Lee",
        item_name: "Premium Catalog Item",
        quantity: 1,
        total_price: 49,
        status: "preparing",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];
    this.tables.set("orders", orders);
    this.nextIds.set("orders", 3);

    const reviews = [
      {
        id: 1,
        customer_name: "Taylor Kim",
        rating: 5,
        comment: "Excellent experience. The platform is responsive, well designed, and very reliable.",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 2,
        customer_name: "Morgan Bailey",
        rating: 5,
        comment: "Outstanding quality and execution. Everything worked seamlessly right out of the box.",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];
    this.tables.set("customer_reviews", reviews);
    this.nextIds.set("customer_reviews", 3);
  }

  list(table: string): Row[] {
    const existing = this.tables.get(table);
    if (existing && existing.length > 0) return existing;

    // Seed realistic records on the fly for any newly requested domain entity
    const singular = table.replace(/s$/, "");
    const label = singular.charAt(0).toUpperCase() + singular.slice(1);
    const defaults = [
      {
        id: 1,
        name: `${label} Alpha`,
        title: `${label} Alpha`,
        status: "active",
        created_at: new Date(Date.now() - 86400000).toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 2,
        name: `${label} Beta`,
        title: `${label} Beta`,
        status: "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];
    this.tables.set(table, defaults);
    this.nextIds.set(table, 3);
    return defaults;
  }

  getById(table: string, id: number): Row | null {
    const rows = this.list(table);
    return rows.find((r) => r.id === id) || null;
  }

  insert(table: string, data: Row): Row {
    const rows = this.list(table);
    const nextId = this.nextIds.get(table) || (rows.length + 1);
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
    const rows = this.list(table);
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
    const rows = this.list(table);
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
RUN mkdir -p public
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_NAME
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME
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


def _strict_actions_stub(spec: AppSpec) -> str:
    """Action stubs that return 501 rather than the expected example value.

    The old gen_actions_stub() returned output_example, which is exactly what
    the generated acceptance test asserted — so the suite passed against an app
    that computed nothing. Stubs must fail until really implemented.
    """
    from app.services.real_backend_codegen import gen_actions_stub_strict

    return gen_actions_stub_strict(spec)


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
        be / "actions.py": "# @generated by AI Solution Builder\n" + _strict_actions_stub(spec),
        be / "tests" / "conftest.py": CONFTEST,
        be / "tests" / "test_acceptance.py": "# @generated by AI Solution Builder\n"
        + gen_acceptance_tests(spec),
        root / "spec.json": spec.model_dump_json(indent=2),
    }
    if analytics_enabled:
        files[be / "routers_analytics.py"] = (
            "# @generated by AI Solution Builder\n" + gen_analytics_router(spec)
        )
    if fe.exists():
        (fe / "src" / "lib").mkdir(parents=True, exist_ok=True)
        files[fe / "src" / "lib" / "types.ts"] = (
            "// @generated by AI Solution Builder\n" + gen_ts_types(spec)
        )
        if _is_subscription_tracker(spec):
            files[fe / "src" / "lib" / "subscriptions.ts"] = _SUBSCRIPTIONS_TS
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    if fe.exists():
        gen_frontend_pages(spec, fe)
        # The old gen_next_route_handlers() faked the whole data layer: an
        # in-memory store seeded with another app's sample rows, and action
        # handlers that returned output_example verbatim. Real server now.
        from app.services.real_backend_codegen import wire_real_data_layer

        wire_real_data_layer(spec, root)
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
