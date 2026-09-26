"""
AI Solution Builder — MVP Starter Templates

Small, deployable app blueprints that seed a Solution's `ai_state` so the
OpenCode MVP builder can generate a working prototype without a multi-step
analysis pipeline. Kept intentionally tiny: one module, two entities, a
handful of endpoints — small enough for free-tier deploys (GitHub + Render).
"""

from typing import Any

from app.services.app_spec import pluralize

# ---------------------------------------------------------------------------
# Preset state is DERIVED, not hand-written
#
# Each preset used to carry ~150 lines of hand-written HLD, LLD, ER diagram,
# API spec and DDL - four copies of the same CRUD boilerplate that had to be
# kept in sync by hand. They drifted: the DDL was written out separately from
# the entity list it claims to describe, so a field could exist in the schema
# but be missing from the generated SQL, and the HLD could advertise tables the
# database never creates.
#
# A preset now declares ONE thing - its entities, their fields and their
# relationships - and every downstream artifact is derived from that single
# source of truth:
#
#     entities + relationships
#        |-> er_diagram            (direct)
#        |-> lld.modules           (one module per entity, endpoints + models)
#        |-> api_spec.endpoints    (CRUD per entity, auth, nested children)
#        |-> generated_schema.ddl  (rendered from the same field definitions)
#        \-> hld                   (overview + component list naming the tables)
#
# Adding a field can no longer leave the DDL or the endpoints behind, and the
# architecture documents can no longer disagree with the schema.
# ---------------------------------------------------------------------------

_TECH_STACK: dict[str, str] = {
    "frontend": "Next.js 15, React, TypeScript, Tailwind CSS, shadcn/ui",
    "backend": "Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2",
    "database": "PostgreSQL 16",
    "auth": "JWT",
}


def _pascal(name: str) -> str:
    """``leave_request`` -> ``LeaveRequest`` (matches the generated models)."""
    return "".join(part.capitalize() for part in name.split("_") if part)


#: Identifiers that are reserved words in PostgreSQL. A domain entity called
#: ``order`` (very common for restaurant/booking apps) generates
#: ``CREATE TABLE order (...)``, which is a syntax error, so they get quoted.
_SQL_RESERVED = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "authorization",
    "between", "binary", "both", "case", "cast", "check", "collate", "column",
    "constraint", "create", "cross", "current_date", "current_role", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "desc",
    "distinct", "do", "else", "end", "except", "false", "for", "foreign", "from",
    "grant", "group", "having", "in", "initially", "intersect", "into", "lateral",
    "leading", "limit", "localtime", "localtimestamp", "not", "null", "offset", "on",
    "only", "or", "order", "placing", "primary", "references", "returning", "select",
    "session_user", "some", "symmetric", "table", "then", "to", "trailing", "true",
    "union", "unique", "user", "using", "variadic", "when", "where", "window", "with",
}


def _sql_ident(name: str) -> str:
    """Quote a SQL identifier only when it collides with a reserved word."""
    return f'"{name}"' if name.lower() in _SQL_RESERVED else name


def _ddl_for(entities: list[dict[str, Any]]) -> str:
    """Render PostgreSQL DDL directly from the entity definitions."""
    tables: list[str] = []
    for entity in entities:
        table = _sql_ident(str(entity["name"]))
        columns: list[str] = []
        for field in entity.get("fields", []):
            fname = _sql_ident(str(field["name"]))
            ftype = str(field.get("type", "TEXT"))
            if field.get("pk"):
                # Only UUID keys can rely on a database-side default.
                suffix = " DEFAULT gen_random_uuid()" if ftype == "UUID" else ""
                columns.append(f"  {fname} {ftype} PRIMARY KEY{suffix}")
                continue
            if field.get("fk"):
                ref_table = _sql_ident(str(field["fk"]).split(".")[0])
                columns.append(
                    f"  {fname} {ftype} NOT NULL REFERENCES {ref_table}(id) ON DELETE CASCADE"
                )
                continue
            default = ""
            if "default" in field:
                literal = field["default"]
                if isinstance(literal, bool):
                    literal = "TRUE" if literal else "FALSE"
                default = f" DEFAULT {literal}"
            columns.append(f"  {fname} {ftype}{default} NOT NULL")
        tables.append(f"CREATE TABLE {table} (\n" + ",\n".join(columns) + "\n);")
    return "\n\n".join(tables)


def _endpoints_for(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Standard REST surface for every entity, plus nested child collections."""
    by_name = {e["name"]: e for e in entities}
    endpoints: list[dict[str, str]] = [
        {"method": "POST", "path": "/api/v1/auth/login", "summary": "Login"},
        {"method": "POST", "path": "/api/v1/auth/register", "summary": "Register"},
    ]
    for entity in entities:
        name = entity["name"]
        plural = pluralize(name)
        label = _pascal(name)
        endpoints.extend(
            [
                {"method": "GET", "path": f"/api/v1/{plural}", "summary": f"List {plural}"},
                {"method": "POST", "path": f"/api/v1/{plural}", "summary": f"Create {label}"},
                {
                    "method": "GET",
                    "path": f"/api/v1/{plural}/{name}_id",
                    "summary": f"Get {label}",
                },
                {
                    "method": "PATCH",
                    "path": f"/api/v1/{plural}/{name}_id",
                    "summary": f"Update {label}",
                },
                {
                    "method": "DELETE",
                    "path": f"/api/v1/{plural}/{name}_id",
                    "summary": f"Delete {label}",
                },
            ]
        )

    # A one-to-many relationship is reachable both as a filtered collection and
    # as a nested route, which is what the generated routers actually expose.
    for rel in relationships:
        parent = rel.get("from")
        child = rel.get("to")
        if not parent or not child or parent not in by_name or child not in by_name:
            continue
        endpoints.append(
            {
                "method": "GET",
                "path": f"/api/v1/{pluralize(parent)}/{parent}_id/{pluralize(child)}",
                "summary": f"List {pluralize(child)} for a {parent}",
            }
        )
    return endpoints


def _derive_template_state(
    *,
    solution_title: str,
    industry: str,
    business_description: str,
    identified_solutions: list[str],
    confirmed_modules: list[str],
    entities: list[dict[str, Any]],
    screen_name: str,
    screen_layout: str,
    screen_components: list[str],
    relationships: list[dict[str, str]] | None = None,
    component_descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a full preset ``ai_state`` from its domain facts.

    The returned dict keeps the exact shape the MVP builder and the artifact
    pipeline already consume, but every architecture artifact is generated from
    ``entities`` rather than transcribed alongside it.
    """
    rels = relationships or []
    endpoints = _endpoints_for(entities, rels)
    table_list = ", ".join(e["name"] for e in entities)

    lld_modules = [
        {
            "name": pluralize(entity["name"]),
            "description": (
                f"CRUD operations and validation for {_pascal(entity['name'])} "
                f"({len(entity.get('fields', []))} fields)"
            ),
            "endpoints": [ep for ep in endpoints if pluralize(entity["name"]) in ep["path"]],
            "models": [
                {
                    "name": _pascal(entity["name"]),
                    "fields": [f["name"] for f in entity.get("fields", [])],
                }
            ],
        }
        for entity in entities
    ]

    descriptions = component_descriptions or {}
    return {
        "business_description": business_description,
        "industry": industry,
        "solution_title": solution_title,
        "identified_solutions": identified_solutions,
        "confirmed_modules": confirmed_modules,
        "hld": {
            "content": {
                "system_overview": (
                    f"{solution_title} is a {industry} application. A Next.js frontend talks to a "
                    f"FastAPI backend over a versioned REST API, backed by PostgreSQL. "
                    f"Persistent domain data: {table_list}."
                ),
                "architecture": "Monolith",
                "components": [
                    {
                        "name": "Web UI",
                        "description": descriptions.get(
                            "web", "Next.js App Router frontend styled with shadcn/ui"
                        ),
                    },
                    {"name": "API", "description": "FastAPI REST backend with Pydantic validation"},
                    {
                        "name": "Database",
                        "description": f"PostgreSQL with tables: {table_list}",
                    },
                ],
                "tech_stack": dict(_TECH_STACK),
            }
        },
        "lld": {"content": {"modules": lld_modules}},
        "er_diagram": {"content": {"entities": entities, "relationships": rels}},
        "api_spec": {
            "content": {
                "base_url": "/api/v1",
                "authentication": "Bearer JWT token",
                "endpoints": endpoints,
            }
        },
        "components": [
            {"name": "Web UI", "type": "frontend", "description": descriptions.get("web", "Next.js App Router frontend")},
            {"name": "API", "type": "backend", "description": "FastAPI REST API"},
            {"name": "Database", "type": "database", "description": f"PostgreSQL ({table_list})"},
        ],
        "generated_schema": {"content": {"ddl": _ddl_for(entities)}},
        "wireframes": [
            {
                "content": {
                    "title": f"{solution_title} Overview",
                    "screens": [
                        {
                            "name": screen_name,
                            "layout": screen_layout,
                            "components": screen_components,
                        }
                    ],
                }
            }
        ],
        "bpmn_flows": [],
    }


_TODO = _derive_template_state(
    solution_title="QuickTodos",
    industry="productivity",
    business_description=(
        "A simple todo list app where users can create projects and track tasks. "
        "Each task has a title, done flag, and belongs to a project."
    ),
    identified_solutions=["task_management"],
    confirmed_modules=["task_management"],
    entities=[
        {
            "name": "project",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "name", "type": "VARCHAR(255)"},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        },
        {
            "name": "task",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "project_id", "type": "UUID", "fk": "project.id"},
                {"name": "title", "type": "VARCHAR(255)"},
                {"name": "done", "type": "BOOLEAN", "default": False},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        },
    ],
    relationships=[{"from": "project", "to": "task", "type": "one_to_many"}],
    screen_name="Dashboard Home",
    screen_layout="Single column list",
    screen_components=[
        "Sidebar: project list with counts",
        "Main area: checkbox tasks for selected project",
        "Input row to add a new task",
    ],
    component_descriptions={"web": "Next.js + Tailwind todo dashboard"},
)


_CALCULATOR = _derive_template_state(
    solution_title="QuickCalc",
    industry="productivity",
    business_description=(
        "An arithmetic calculator that evaluates an expression and keeps a "
        "searchable history of previous calculations."
    ),
    identified_solutions=["calculator"],
    confirmed_modules=["calculator"],
    entities=[
        {
            "name": "calculation",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "expression", "type": "VARCHAR(255)"},
                {"name": "result", "type": "VARCHAR(50)"},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        }
    ],
    screen_name="Calculator Page",
    screen_layout="Keypad over history list",
    screen_components=[
        "Expression display",
        "Numeric keypad",
        "Reversible calculation history list",
    ],
    component_descriptions={"web": "Next.js + Tailwind calculator keypad"},
)


_PORTFOLIO = _derive_template_state(
    solution_title="MyPortfolio",
    industry="personal",
    business_description=(
        "A personal portfolio site with a landing page, a project showcase and a "
        "contact form that stores enquiries."
    ),
    identified_solutions=["portfolio"],
    confirmed_modules=["portfolio"],
    entities=[
        {
            "name": "contact_message",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "name", "type": "VARCHAR(255)"},
                {"name": "email", "type": "VARCHAR(255)"},
                {"name": "message", "type": "TEXT"},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        }
    ],
    screen_name="Landing Page",
    screen_layout="Hero, project grid, contact form",
    screen_components=[
        "Hero section with introduction",
        "Responsive project showcase grid",
        "Contact form posting to the API",
    ],
    component_descriptions={"web": "Next.js + Tailwind landing page"},
)


_RESTAURANT_ORDERING = _derive_template_state(
    solution_title="TableServe",
    industry="food_service",
    business_description=(
        "A restaurant ordering system with a customer menu storefront, a cart, and "
        "a kitchen board where staff track incoming orders through preparation."
    ),
    identified_solutions=["menu_ordering"],
    confirmed_modules=["menu_ordering", "kitchen_board"],
    entities=[
        {
            "name": "dish",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "name", "type": "VARCHAR(255)"},
                {"name": "category", "type": "VARCHAR(100)"},
                {"name": "price", "type": "FLOAT"},
                {"name": "description", "type": "TEXT"},
                {"name": "dietary", "type": "VARCHAR(100)"},
                {"name": "is_available", "type": "BOOLEAN", "default": True},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        },
        {
            "name": "order",
            "fields": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "table_number", "type": "VARCHAR(255)"},
                {"name": "total_amount", "type": "FLOAT"},
                {"name": "status", "type": "VARCHAR(50)"},
                {"name": "created_at", "type": "TIMESTAMPTZ"},
            ],
        },
    ],
    screen_name="Customer Storefront",
    screen_layout="Menu grid with cart drawer",
    screen_components=[
        "Menu grid grouped by category with dietary labels",
        "Cart drawer with live total",
        "Kitchen orders board with status transitions",
    ],
    component_descriptions={
        "web": "Next.js menu storefront with cart drawer and kitchen board"
    },
)


class MVPTemplate:
    """Metadata for one starter template plus its ready-to-build ai_state."""

    def __init__(
        self,
        slug: str,
        title: str,
        description: str,
        ai_state: dict[str, Any],
    ) -> None:
        self.slug = slug
        self.title = title
        self.description = description
        self._ai_state = ai_state

    def build_ai_state(self) -> dict[str, Any]:
        """Return a deep copy so callers never mutate the shared preset."""
        import copy

        return copy.deepcopy(self._ai_state)

    def to_dict(self) -> dict[str, str]:
        return {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "app_name": self._ai_state.get("solution_title", self.title),
            "industry": self._ai_state.get("industry", "general"),
        }


TEMPLATES: list[MVPTemplate] = [
    MVPTemplate(
        slug="todo",
        title="Todo App",
        description="Projects and tasks with check-off tracking.",
        ai_state=_TODO,
    ),
    MVPTemplate(
        slug="calculator",
        title="Calculator",
        description="Arithmetic calculator with history.",
        ai_state=_CALCULATOR,
    ),
    MVPTemplate(
        slug="portfolio",
        title="Portfolio Website",
        description="Landing page, project showcase, and contact form.",
        ai_state=_PORTFOLIO,
    ),
    MVPTemplate(
        slug="restaurant_ordering",
        title="Restaurant Menu & Ordering",
        description="Customer menu storefront, dynamic cart drawer, and live kitchen orders admin dashboard.",
        ai_state=_RESTAURANT_ORDERING,
    ),
]

TEMPLATE_BY_SLUG: dict[str, MVPTemplate] = {t.slug: t for t in TEMPLATES}


def get_template(slug: str) -> MVPTemplate | None:
    return TEMPLATE_BY_SLUG.get(slug)


def list_templates() -> list[dict[str, str]]:
    return [t.to_dict() for t in TEMPLATES]


_API_CLIENT_TS = """// Typed API client. Base URL comes from NEXT_PUBLIC_API_URL.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api/v1" : "http://localhost:8000/api/v1");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    throw new ApiError(
      0,
      `Network connection failed (${API_BASE}). Ensure the backend service is running and accessible.`
    );
  }
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body.slice(0, 500));
  }
  if (res.status === 204) {
    return {} as T;
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
"""


def apply_template_files(build_dir: Any, slug: str, app_title: str | None = None) -> None:
    """Instantiate the complete working files for a starter template directly into build_dir."""
    from pathlib import Path

    root = Path(build_dir)
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"
    title = app_title or slug.title()

    # Ensure frontend/src/lib/api.ts is always present for the template UI
    lib_dir = frontend_dir / "src" / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / "api.ts").write_text(_API_CLIENT_TS, encoding="utf-8")

    # Ensure frontend/public exists for Next.js Docker build
    pub_dir = frontend_dir / "public"
    pub_dir.mkdir(parents=True, exist_ok=True)
    (pub_dir / ".gitkeep").touch()

    if slug == "todo":
        _apply_todo_template(backend_dir, frontend_dir, title)
    elif slug == "calculator":
        _apply_calculator_template(backend_dir, frontend_dir, title)
    elif slug == "portfolio":
        _apply_portfolio_template(backend_dir, frontend_dir, title)
    elif slug == "restaurant_ordering":
        _apply_restaurant_template(backend_dir, frontend_dir, title)


def _apply_todo_template(backend_dir: Any, frontend_dir: Any, title: str) -> None:
    from pathlib import Path

    b_dir = Path(backend_dir)
    f_dir = Path(frontend_dir)

    models_content = '''"""SQLAlchemy models for Todo app."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from typing import List
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "project"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "task"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    project: Mapped[Project] = relationship("Project", back_populates="tasks")
'''
    (b_dir / "models.py").write_text(models_content, encoding="utf-8")

    schemas_content = '''"""Pydantic schemas for Todo app."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class TaskBase(BaseModel):
    title: str
    done: bool = False

class TaskCreate(TaskBase):
    project_id: uuid.UUID

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class TaskRead(TaskBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ProjectBase(BaseModel):
    name: str

class ProjectCreate(ProjectBase):
    pass

class ProjectRead(ProjectBase):
    id: uuid.UUID
    created_at: datetime
    tasks: List[TaskRead] = []
    model_config = ConfigDict(from_attributes=True)
'''
    (b_dir / "schemas.py").write_text(schemas_content, encoding="utf-8")

    routers_content = '''"""API routers for Todo app."""
from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, text
try:
    from .core.config import settings
    from .deps import SessionDep
    from .models import Project, Task
    from .schemas import ProjectCreate, ProjectRead, TaskCreate, TaskRead, TaskUpdate
except (ImportError, ValueError):
    from core.config import settings
    from deps import SessionDep
    from models import Project, Task
    from schemas import ProjectCreate, ProjectRead, TaskCreate, TaskRead, TaskUpdate

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}

@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}

@router.get("/projects", response_model=List[ProjectRead])
async def list_projects(session: SessionDep) -> List[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())

@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, session: SessionDep) -> Project:
    project = Project(name=payload.name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project

@router.get("/projects/{project_id}/tasks", response_model=List[TaskRead])
async def list_tasks(project_id: uuid.UUID, session: SessionDep) -> List[Task]:
    result = await session.execute(select(Task).where(Task.project_id == project_id).order_by(Task.created_at.asc()))
    return list(result.scalars().all())

@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, session: SessionDep) -> Task:
    task = Task(project_id=payload.project_id, title=payload.title, done=payload.done)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task

@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, session: SessionDep) -> Task:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.title is not None:
        task.title = payload.title
    if payload.done is not None:
        task.done = payload.done
    await session.commit()
    await session.refresh(task)
    return task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:
    task = await session.get(Task, task_id)
    if task:
        await session.delete(task)
        await session.commit()
    return {"ok": True}
'''
    (b_dir / "routers.py").write_text(routers_content, encoding="utf-8")

    page_content = """"use client";

import React, { useState, useEffect } from "react";
import { api } from "../lib/api";

interface Task {
  id: string;
  project_id: string;
  title: string;
  done: boolean;
}

interface Project {
  id: string;
  name: string;
  tasks?: Task[];
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([
    { id: "p1", name: "Default Project" },
  ]);
  const [activeProject, setActiveProject] = useState<string>("p1");
  const [tasks, setTasks] = useState<Task[]>([
    { id: "t1", project_id: "p1", title: "Welcome to __APP_TITLE__!", done: false },
    { id: "t2", project_id: "p1", title: "Mark tasks complete with checkboxes", done: true },
  ]);
  const [newTitle, setNewTitle] = useState("");
  const [newProjectName, setNewProjectName] = useState("");

  useEffect(() => {
    api.get<Project[]>("/projects")
      .then((res) => {
        if (res && res.length > 0) {
          setProjects(res);
          setActiveProject(res[0].id);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeProject || activeProject === "p1") return;
    api.get<Task[]>(`/projects/${activeProject}/tasks`)
      .then((res) => {
        if (res) setTasks(res);
      })
      .catch(() => undefined);
  }, [activeProject]);

  const addTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const newTask: Task = {
      id: "task-" + Date.now(),
      project_id: activeProject,
      title: newTitle.trim(),
      done: false,
    };
    setTasks((prev) => [...prev, newTask]);
    setNewTitle("");
    api.post<Task>("/tasks", { project_id: activeProject, title: newTask.title, done: false })
      .catch(() => undefined);
  };

  const toggleTask = (taskId: string, current: boolean) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, done: !current } : t))
    );
    api.patch(`/tasks/${taskId}`, { done: !current }).catch(() => undefined);
  };

  const deleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
    api.del(`/tasks/${taskId}`).catch(() => undefined);
  };

  const addProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    const newProj: Project = { id: "proj-" + Date.now(), name: newProjectName.trim() };
    setProjects((prev) => [...prev, newProj]);
    setActiveProject(newProj.id);
    setNewProjectName("");
    api.post<Project>("/projects", { name: newProj.name }).catch(() => undefined);
  };

  const currentTasks = tasks.filter((t) => t.project_id === activeProject);

  return (
    <main className="mx-auto max-w-4xl px-4 py-12">
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="flex items-center justify-between border-b pb-6">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900">__APP_TITLE__</h1>
            <p className="mt-1 text-sm text-slate-500">Fast, streamlined task & project management</p>
          </div>
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600 border border-indigo-100">
            MVP Ready
          </span>
        </div>

        {/* Project Selector */}
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setActiveProject(p.id)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeProject === p.id
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-200"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {p.name}
            </button>
          ))}
          <form onSubmit={addProject} className="flex items-center gap-1">
            <input
              type="text"
              placeholder="+ New Project"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500"
            />
          </form>
        </div>

        {/* Add Task */}
        <form onSubmit={addTask} className="mt-6 flex gap-2">
          <input
            type="text"
            placeholder="Add a new task..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-600 shadow-sm"
          />
          <button
            type="submit"
            className="rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-indigo-700 transition-colors"
          >
            Add Task
          </button>
        </form>

        {/* Task List */}
        <div className="mt-6 divide-y divide-slate-100">
          {currentTasks.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-400">
              No tasks in this project yet. Add one above!
            </div>
          ) : (
            currentTasks.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3 group">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={t.done}
                    onChange={() => toggleTask(t.id, t.done)}
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className={`text-sm ${t.done ? "line-through text-slate-400" : "text-slate-700"}`}>
                    {t.title}
                  </span>
                </div>
                <button
                  onClick={() => deleteTask(t.id)}
                  className="opacity-0 group-hover:opacity-100 text-xs text-rose-500 hover:text-rose-700 transition-opacity"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
""".replace("__APP_TITLE__", title)
    (f_dir / "src" / "app" / "page.tsx").write_text(page_content, encoding="utf-8")


def _apply_calculator_template(backend_dir: Any, frontend_dir: Any, title: str) -> None:
    from pathlib import Path

    b_dir = Path(backend_dir)
    f_dir = Path(frontend_dir)

    models_content = '''"""SQLAlchemy models for Calculator app."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Calculation(Base):
    __tablename__ = "calculation"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expression: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
'''
    (b_dir / "models.py").write_text(models_content, encoding="utf-8")

    schemas_content = '''"""Pydantic schemas for Calculator app."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CalculationEvaluate(BaseModel):
    expression: str

class CalculationRead(BaseModel):
    id: uuid.UUID
    expression: str
    result: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
'''
    (b_dir / "schemas.py").write_text(schemas_content, encoding="utf-8")

    routers_content = '''"""API routers for Calculator app."""
from __future__ import annotations
import ast
import operator as op
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, text
try:
    from .core.config import settings
    from .deps import SessionDep
    from .models import Calculation
    from .schemas import CalculationEvaluate, CalculationRead
except (ImportError, ValueError):
    from core.config import settings
    from deps import SessionDep
    from models import Calculation
    from schemas import CalculationEvaluate, CalculationRead

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}

@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}

_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

def _eval_expr(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        elif isinstance(node, ast.BinOp):
            return _OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return _OPERATORS[type(node.op)](_eval(node.operand))
        else:
            raise ValueError("Unsupported operation")
    tree = ast.parse(expr.strip(), mode="eval")
    return _eval(tree.body)

@router.post("/calculations/evaluate", response_model=CalculationRead, status_code=status.HTTP_201_CREATED)
async def evaluate_calculation(payload: CalculationEvaluate, session: SessionDep) -> Calculation:
    try:
        val = _eval_expr(payload.expression)
        res_str = str(int(val)) if val == int(val) else f"{val:.4f}".rstrip("0").rstrip(".")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid arithmetic expression: {exc}")
    calc = Calculation(expression=payload.expression, result=res_str)
    session.add(calc)
    await session.commit()
    await session.refresh(calc)
    return calc

@router.get("/calculations", response_model=List[CalculationRead])
async def list_calculations(session: SessionDep) -> List[Calculation]:
    result = await session.execute(select(Calculation).order_by(Calculation.created_at.desc()).limit(50))
    return list(result.scalars().all())

@router.delete("/calculations/{calc_id}")
async def delete_calculation(calc_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:
    calc = await session.get(Calculation, calc_id)
    if calc:
        await session.delete(calc)
        await session.commit()
    return {"ok": True}
'''
    (b_dir / "routers.py").write_text(routers_content, encoding="utf-8")

    page_content = """"use client";

import React, { useState, useEffect } from "react";
import { api } from "../lib/api";

interface CalcRecord {
  id: string;
  expression: string;
  result: string;
}

export default function Home() {
  const [expr, setExpr] = useState("");
  const [history, setHistory] = useState<CalcRecord[]>([]);

  useEffect(() => {
    api.get<CalcRecord[]>("/calculations")
      .then((res) => {
        if (res) setHistory(res);
      })
      .catch(() => undefined);
  }, []);

  const press = (val: string) => {
    if (val === "C") {
      setExpr("");
    } else if (val === "=") {
      calculate();
    } else {
      setExpr((prev) => prev + val);
    }
  };

  const calculate = async () => {
    if (!expr.trim()) return;
    try {
      const clean = expr.replace(/[^0-9+\\-*\\/().]/g, "");
      const res = Function('"use strict";return (' + clean + ')')();
      const resStr = String(res);
      setHistory((prev) => [{ id: "c-" + Date.now(), expression: expr, result: resStr }, ...prev]);
      setExpr(resStr);
      api.post<CalcRecord>("/calculations/evaluate", { expression: clean }).catch(() => undefined);
    } catch {
      setExpr("Error");
    }
  };

  return (
    <main className="mx-auto max-w-xl px-4 py-12">
      <div className="rounded-3xl border border-slate-800 bg-slate-950 p-6 text-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
          <h1 className="text-xl font-bold tracking-tight text-indigo-400">__APP_TITLE__</h1>
          <span className="text-xs text-slate-500">Persistent Ledger</span>
        </div>

        {/* Display */}
        <div className="rounded-2xl bg-slate-900 p-4 text-right mb-6 border border-slate-800 shadow-inner">
          <div className="min-h-[2.5rem] font-mono text-3xl font-bold text-white tracking-wider overflow-x-auto">
            {expr || "0"}
          </div>
        </div>

        {/* Keypad */}
        <div className="grid grid-cols-4 gap-3 font-semibold text-lg">
          {["C", "(", ")", "/"].map((k) => (
            <button
              key={k}
              onClick={() => press(k)}
              className="py-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-400 transition-colors shadow-sm"
            >
              {k}
            </button>
          ))}
          {["7", "8", "9", "*"].map((k) => (
            <button
              key={k}
              onClick={() => press(k)}
              className={`py-3.5 rounded-xl ${
                k === "*" ? "bg-slate-800 text-indigo-400 hover:bg-slate-700" : "bg-slate-900 hover:bg-slate-850 text-white"
              } transition-colors shadow-sm`}
            >
              {k}
            </button>
          ))}
          {["4", "5", "6", "-"].map((k) => (
            <button
              key={k}
              onClick={() => press(k)}
              className={`py-3.5 rounded-xl ${
                k === "-" ? "bg-slate-800 text-indigo-400 hover:bg-slate-700" : "bg-slate-900 hover:bg-slate-850 text-white"
              } transition-colors shadow-sm`}
            >
              {k}
            </button>
          ))}
          {["1", "2", "3", "+"].map((k) => (
            <button
              key={k}
              onClick={() => press(k)}
              className={`py-3.5 rounded-xl ${
                k === "+" ? "bg-slate-800 text-indigo-400 hover:bg-slate-700" : "bg-slate-900 hover:bg-slate-850 text-white"
              } transition-colors shadow-sm`}
            >
              {k}
            </button>
          ))}
          {["0", ".", "BS", "="].map((k) => (
            <button
              key={k}
              onClick={() => {
                if (k === "BS") setExpr((prev) => prev.slice(0, -1));
                else press(k);
              }}
              className={`py-3.5 rounded-xl ${
                k === "="
                  ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30"
                  : "bg-slate-900 hover:bg-slate-850 text-white"
              } transition-colors shadow-sm`}
            >
              {k}
            </button>
          ))}
        </div>

        {/* History */}
        <div className="mt-8 border-t border-slate-800 pt-4">
          <span className="text-xs uppercase tracking-wider text-slate-500 font-semibold block mb-2">History</span>
          <div className="max-h-40 overflow-y-auto divide-y divide-slate-900 text-xs font-mono">
            {history.length === 0 ? (
              <p className="text-slate-600 py-2">No past calculations recorded.</p>
            ) : (
              history.map((h) => (
                <div
                  key={h.id}
                  onClick={() => setExpr(h.result)}
                  className="flex justify-between py-2 px-1 hover:bg-slate-900/60 cursor-pointer rounded transition-colors"
                >
                  <span className="text-slate-400">{h.expression}</span>
                  <span className="text-emerald-400 font-bold">= {h.result}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
""".replace("__APP_TITLE__", title)
    (f_dir / "src" / "app" / "page.tsx").write_text(page_content, encoding="utf-8")


def _apply_portfolio_template(backend_dir: Any, frontend_dir: Any, title: str) -> None:
    from pathlib import Path

    b_dir = Path(backend_dir)
    f_dir = Path(frontend_dir)

    models_content = '''"""SQLAlchemy models for Portfolio app."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ContactMessage(Base):
    __tablename__ = "contact_message"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
'''
    (b_dir / "models.py").write_text(models_content, encoding="utf-8")

    schemas_content = '''"""Pydantic schemas for Portfolio app."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ContactMessageCreate(BaseModel):
    name: str
    email: str
    message: str

class ContactMessageRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
'''
    (b_dir / "schemas.py").write_text(schemas_content, encoding="utf-8")

    routers_content = '''"""API routers for Portfolio app."""
from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, status
from sqlalchemy import select, text
try:
    from .core.config import settings
    from .deps import SessionDep
    from .models import ContactMessage
    from .schemas import ContactMessageCreate, ContactMessageRead
except (ImportError, ValueError):
    from core.config import settings
    from deps import SessionDep
    from models import ContactMessage
    from schemas import ContactMessageCreate, ContactMessageRead

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}

@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}

@router.post("/contact", response_model=ContactMessageRead, status_code=status.HTTP_201_CREATED)
async def submit_contact(payload: ContactMessageCreate, session: SessionDep) -> ContactMessage:
    msg = ContactMessage(name=payload.name, email=payload.email, message=payload.message)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg

@router.get("/contact", response_model=List[ContactMessageRead])
async def list_contact_messages(session: SessionDep) -> List[ContactMessage]:
    result = await session.execute(select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(100))
    return list(result.scalars().all())
'''
    (b_dir / "routers.py").write_text(routers_content, encoding="utf-8")

    page_content = """"use client";

import React, { useState } from "react";
import { api } from "../lib/api";

export default function Home() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !message) return;
    setSubmitted(true);
    api.post("/contact", { name, email, message }).catch(() => undefined);
  };

  const projects = [
    {
      title: "AI Solution Builder",
      desc: "Multi-agent autonomous software architecture synthesizer with one-click fullstack deployments.",
      tags: ["FastAPI", "Next.js", "PostgreSQL", "Docker"],
    },
    {
      title: "Cloud Native Event Engine",
      desc: "Distributed event mesh handling millions of daily messages with zero data loss guarantees.",
      tags: ["Python", "Redis", "Kafka", "Kubernetes"],
    },
    {
      title: "Modern FinTech Dashboard",
      desc: "High-frequency portfolio analytics with real-time WebSockets and sub-millisecond execution.",
      tags: ["TypeScript", "React", "Tailwind CSS"],
    },
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5 text-xs font-semibold text-indigo-300 mb-6">
          <span>Software Engineer & Solutions Architect</span>
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight text-white sm:text-6xl">
          __APP_TITLE__
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base text-slate-400">
          Building resilient, high-performance distributed systems and delightful user experiences.
        </p>
      </section>

      {/* Projects */}
      <section className="mx-auto max-w-5xl px-6 py-12">
        <h2 className="text-2xl font-bold text-white mb-6">Featured Projects</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {projects.map((p, i) => (
            <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur flex flex-col justify-between hover:border-indigo-500/50 transition-colors">
              <div>
                <h3 className="text-lg font-bold text-white mb-2">{p.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed mb-4">{p.desc}</p>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-2">
                {p.tags.map((t, j) => (
                  <span key={j} className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-300">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Contact Form */}
      <section className="mx-auto max-w-2xl px-6 py-16">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
          <h2 className="text-2xl font-bold text-white mb-2">Get in Touch</h2>
          <p className="text-xs text-slate-400 mb-6">Send a message directly to my inbox.</p>

          {submitted ? (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-center text-xs text-emerald-300">
              Thank you! Your message has been recorded.
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
                  placeholder="Your Name"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
                  placeholder="your@email.com"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Message</label>
                <textarea
                  required
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none"
                  placeholder="Tell me about your project..."
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-indigo-600 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-colors"
              >
                Send Message
              </button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
""".replace("__APP_TITLE__", title)
    (f_dir / "src" / "app" / "page.tsx").write_text(page_content, encoding="utf-8")


def _apply_restaurant_template(backend_dir: Any, frontend_dir: Any, title: str) -> None:
    from pathlib import Path

    from app.services.mvp_builder import (
        _generate_admin_orders_page,
        _generate_dish_management_page,
        _generate_restaurant_storefront_page,
    )

    b_dir = Path(backend_dir)
    f_dir = Path(frontend_dir)

    models_content = '''"""SQLAlchemy models for Restaurant Ordering app."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Dish(Base):
    __tablename__ = "dish"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Mains")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=12.99)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dietary: Mapped[str] = mapped_column(String(100), nullable=False, default="Chef Special")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

class Order(Base):
    __tablename__ = "order"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_number: Mapped[str] = mapped_column(String(255), nullable=False, default="Table 1")
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
'''
    (b_dir / "models.py").write_text(models_content, encoding="utf-8")

    schemas_content = '''"""Pydantic schemas for Restaurant Ordering app."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class DishBase(BaseModel):
    name: str
    category: str = "Mains"
    price: float = 12.99
    description: str = ""
    dietary: str = "Chef Special"
    is_available: bool = True

class DishCreate(DishBase):
    pass

class DishRead(DishBase):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    table_number: str
    total_amount: float
    status: str = "Pending"

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    table_number: Optional[str] = None
    total_amount: Optional[float] = None

class OrderRead(OrderBase):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
'''
    (b_dir / "schemas.py").write_text(schemas_content, encoding="utf-8")

    routers_content = '''"""API routers for Restaurant Ordering app."""
from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, text
try:
    from .core.config import settings
    from .deps import SessionDep
    from .models import Dish, Order
    from .schemas import DishCreate, DishRead, OrderCreate, OrderRead, OrderUpdate
except (ImportError, ValueError):
    from core.config import settings
    from deps import SessionDep
    from models import Dish, Order
    from schemas import DishCreate, DishRead, OrderCreate, OrderRead, OrderUpdate

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}

@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}

@router.get("/dishes", response_model=List[DishRead])
async def list_dishes(session: SessionDep) -> List[Dish]:
    res = await session.execute(select(Dish).order_by(Dish.created_at.asc()))
    items = list(res.scalars().all())
    if not items:
        seeds = [
            Dish(name="Truffle Mushroom Risotto", category="Mains", price=19.5, description="Creamy arborio rice infused with black truffle emulsion and wild forest mushrooms.", dietary="Vegetarian"),
            Dish(name="Artisan Margherita Pizza", category="Mains", price=14.0, description="San Marzano tomato base, fresh buffalo mozzarella, fragrant basil, cold-pressed olive oil.", dietary="Vegetarian"),
            Dish(name="Crispy Calamari & Herb Aioli", category="Starters", price=12.0, description="Golden fried calamari rings dusted with sea salt, smoked paprika, and garlic aioli.", dietary="Seafood"),
            Dish(name="Charred Burrata & Peach Salad", category="Starters", price=13.5, description="Handcrafted Italian burrata with sweet grilled peaches, balsamic glaze, and micro arugula.", dietary="Gluten-Free"),
            Dish(name="Classic Tiramisu al Mascarpone", category="Desserts", price=9.5, description="Espresso-soaked savoiardi ladyfingers layered with velvety mascarpone crema.", dietary="Signature"),
            Dish(name="Cold Brew Espresso Tonic", category="Beverages", price=5.5, description="Single-origin Ethiopian cold brew layered over crisp citrus tonic water with rosemary.", dietary="Vegan"),
        ]
        for s in seeds:
            session.add(s)
        await session.commit()
        for s in seeds:
            await session.refresh(s)
        return seeds
    return items

@router.post("/dishes", response_model=DishRead, status_code=status.HTTP_201_CREATED)
async def create_dish(payload: DishCreate, session: SessionDep) -> Dish:
    dish = Dish(**payload.model_dump())
    session.add(dish)
    await session.commit()
    await session.refresh(dish)
    return dish

@router.delete("/dishes/{dish_id}")
async def delete_dish(dish_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:
    dish = await session.get(Dish, dish_id)
    if dish:
        await session.delete(dish)
        await session.commit()
    return {"ok": True}

@router.get("/orders", response_model=List[OrderRead])
async def list_orders(session: SessionDep) -> List[Order]:
    res = await session.execute(select(Order).order_by(Order.created_at.desc()))
    items = list(res.scalars().all())
    if not items:
        seeds = [
            Order(table_number="Table 4 (Alex M.)", total_amount=43.5, status="In Kitchen"),
            Order(table_number="Table 7 (Sarah K.)", total_amount=29.0, status="Pending"),
            Order(table_number="Takeout #104 (David)", total_amount=19.5, status="Ready"),
        ]
        for s in seeds:
            session.add(s)
        await session.commit()
        for s in seeds:
            await session.refresh(s)
        return seeds
    return items

@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, session: SessionDep) -> Order:
    order = Order(**payload.model_dump())
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order

@router.patch("/orders/{order_id}", response_model=OrderRead)
async def update_order(order_id: uuid.UUID, payload: OrderUpdate, session: SessionDep) -> Order:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(order, k, v)
    await session.commit()
    await session.refresh(order)
    return order

@router.delete("/orders/{order_id}")
async def delete_order(order_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:
    order = await session.get(Order, order_id)
    if order:
        await session.delete(order)
        await session.commit()
    return {"ok": True}
'''
    (b_dir / "routers.py").write_text(routers_content, encoding="utf-8")

    (f_dir / "src" / "app" / "page.tsx").write_text(
        _generate_restaurant_storefront_page(title), encoding="utf-8"
    )

    orders_dir = f_dir / "src" / "app" / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    (orders_dir / "page.tsx").write_text(_generate_admin_orders_page(title), encoding="utf-8")

    dishes_dir = f_dir / "src" / "app" / "dishes"
    dishes_dir.mkdir(parents=True, exist_ok=True)
    (dishes_dir / "page.tsx").write_text(_generate_dish_management_page(title), encoding="utf-8")
