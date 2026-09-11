"""
AI Solution Builder — MVP Starter Templates

Small, deployable app blueprints that seed a Solution's `ai_state` so the
OpenCode MVP builder can generate a working prototype without a multi-step
analysis pipeline. Kept intentionally tiny: one module, two entities, a
handful of endpoints — small enough for free-tier deploys (GitHub + Render).
"""

from typing import Any

_TODO = {
    "business_description": (
        "A simple todo list app where users can create projects and track tasks. "
        "Each task has a title, done flag, and belongs to a project."
    ),
    "industry": "productivity",
    "solution_title": "QuickTodos",
    "identified_solutions": ["task_management"],
    "confirmed_modules": ["task_management"],
    "hld": {
        "content": {
            "system_overview": (
                "QuickTodos is a minimal single-user todo tracker. Next.js frontend, "
                "FastAPI backend, PostgreSQL database, JWT auth."
            ),
            "architecture": "Monolith",
            "components": [
                {"name": "Web UI", "description": "Next.js + Tailwind todo dashboard"},
                {"name": "API", "description": "FastAPI CRUD backend"},
                {"name": "Database", "description": "PostgreSQL with project + task tables"},
            ],
            "tech_stack": {
                "frontend": "Next.js 15, React, TypeScript, Tailwind CSS",
                "backend": "Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2",
                "database": "PostgreSQL 16",
                "auth": "JWT",
            },
        }
    },
    "lld": {
        "content": {
            "modules": [
                {
                    "name": "task_management",
                    "description": "CRUD for projects and tasks with toggle-done",
                    "endpoints": [
                        {
                            "method": "GET",
                            "path": "/api/v1/projects",
                            "description": "List projects",
                        },
                        {
                            "method": "POST",
                            "path": "/api/v1/projects",
                            "description": "Create project",
                        },
                        {
                            "method": "GET",
                            "path": "/api/v1/projects/{project_id}/tasks",
                            "description": "List tasks",
                        },
                        {"method": "POST", "path": "/api/v1/tasks", "description": "Create task"},
                        {
                            "method": "PATCH",
                            "path": "/api/v1/tasks/{task_id}",
                            "description": "Update task",
                        },
                        {
                            "method": "DELETE",
                            "path": "/api/v1/tasks/{task_id}",
                            "description": "Delete task",
                        },
                    ],
                    "models": [
                        {"name": "Project", "fields": ["id", "name", "created_at"]},
                        {
                            "name": "Task",
                            "fields": ["id", "project_id", "title", "done", "created_at"],
                        },
                    ],
                }
            ],
            "data_flow": "Frontend -> FastAPI -> PostgreSQL",
        }
    },
    "er_diagram": {
        "content": {
            "entities": [
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
            "relationships": [{"from": "project", "to": "task", "type": "one_to_many"}],
        }
    },
    "api_spec": {
        "content": {
            "base_url": "/api/v1",
            "authentication": "Bearer JWT token",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/auth/login", "summary": "Login"},
                {"method": "POST", "path": "/api/v1/auth/register", "summary": "Register"},
                {"method": "GET", "path": "/api/v1/projects", "summary": "List projects"},
                {"method": "POST", "path": "/api/v1/projects", "summary": "Create project"},
                {
                    "method": "GET",
                    "path": "/api/v1/projects/{project_id}/tasks",
                    "summary": "List tasks",
                },
                {"method": "POST", "path": "/api/v1/tasks", "summary": "Create task"},
                {"method": "PATCH", "path": "/api/v1/tasks/{task_id}", "summary": "Update task"},
                {"method": "DELETE", "path": "/api/v1/tasks/{task_id}", "summary": "Delete task"},
            ],
        }
    },
    "generated_schema": {
        "content": {
            "ddl": (
                "CREATE TABLE project (\n"
                "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n"
                "  name VARCHAR(255) NOT NULL,\n"
                "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                ");\n\n"
                "CREATE TABLE task (\n"
                "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n"
                "  project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,\n"
                "  title VARCHAR(255) NOT NULL,\n"
                "  done BOOLEAN DEFAULT FALSE NOT NULL,\n"
                "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                ");"
            )
        }
    },
    "wireframes": [
        {
            "content": {
                "title": "Todo Dashboard",
                "screens": [
                    {
                        "name": "Dashboard Home",
                        "layout": "Single column list",
                        "components": [
                            "Sidebar: project list with counts",
                            "Main area: checkbox tasks for selected project",
                            "Input row to add a new task",
                        ],
                    }
                ],
            }
        }
    ],
    "bpmn_flows": [],
}

_CALCULATOR = {
    "business_description": (
        "A clean web calculator supporting the four basic arithmetic operations "
        "with a browsing history of past calculations."
    ),
    "industry": "productivity",
    "solution_title": "QuickCalc",
    "identified_solutions": ["calculator"],
    "confirmed_modules": ["calculator"],
    "hld": {
        "content": {
            "system_overview": (
                "QuickCalc is a minimal web calculator. Next.js frontend, FastAPI "
                "backend storing a calculation history table, JWT auth."
            ),
            "architecture": "Monolith",
            "components": [
                {"name": "Web UI", "description": "Next.js + Tailwind calculator keypad"},
                {"name": "API", "description": "FastAPI evaluate + history endpoints"},
                {"name": "Database", "description": "PostgreSQL calculation history table"},
            ],
            "tech_stack": {
                "frontend": "Next.js 15, React, TypeScript, Tailwind CSS",
                "backend": "Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2",
                "database": "PostgreSQL 16",
                "auth": "JWT",
            },
        }
    },
    "lld": {
        "content": {
            "modules": [
                {
                    "name": "calculator",
                    "description": "Evaluate arithmetic expressions and store history",
                    "endpoints": [
                        {
                            "method": "POST",
                            "path": "/api/v1/calculations/evaluate",
                            "description": "Evaluate expression",
                        },
                        {
                            "method": "GET",
                            "path": "/api/v1/calculations",
                            "description": "List calculation history",
                        },
                        {
                            "method": "DELETE",
                            "path": "/api/v1/calculations/{id}",
                            "description": "Delete history entry",
                        },
                    ],
                    "models": [
                        {
                            "name": "Calculation",
                            "fields": ["id", "expression", "result", "created_at"],
                        },
                    ],
                }
            ],
            "data_flow": "Frontend -> FastAPI -> PostgreSQL",
        }
    },
    "er_diagram": {
        "content": {
            "entities": [
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
            "relationships": [],
        }
    },
    "api_spec": {
        "content": {
            "base_url": "/api/v1",
            "authentication": "Bearer JWT token",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/auth/login", "summary": "Login"},
                {"method": "POST", "path": "/api/v1/auth/register", "summary": "Register"},
                {
                    "method": "POST",
                    "path": "/api/v1/calculations/evaluate",
                    "summary": "Evaluate expression",
                },
                {"method": "GET", "path": "/api/v1/calculations", "summary": "List history"},
                {
                    "method": "DELETE",
                    "path": "/api/v1/calculations/{id}",
                    "summary": "Delete history entry",
                },
            ],
        }
    },
    "generated_schema": {
        "content": {
            "ddl": (
                "CREATE TABLE calculation (\n"
                "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n"
                "  expression VARCHAR(255) NOT NULL,\n"
                "  result VARCHAR(50) NOT NULL,\n"
                "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                ");"
            )
        }
    },
    "wireframes": [
        {
            "content": {
                "title": "Calculator",
                "screens": [
                    {
                        "name": "Calculator Page",
                        "layout": "Centered keypad",
                        "components": [
                            "Display showing current expression and result",
                            "Digit and operator buttons (0-9, + - * / =, C)",
                            "History panel listing recent calculations",
                        ],
                    }
                ],
            }
        }
    ],
    "bpmn_flows": [],
}

_PORTFOLIO = {
    "business_description": (
        "A personal portfolio website with a landing page, project showcase, "
        "and a simple contact form that stores messages. No backend CRUD beyond "
        "the contact message table."
    ),
    "industry": "personal",
    "solution_title": "MyPortfolio",
    "identified_solutions": ["portfolio"],
    "confirmed_modules": ["portfolio"],
    "hld": {
        "content": {
            "system_overview": (
                "A personal portfolio site. Next.js frontend with Tailwind, FastAPI "
                "backend exposing a public contact form endpoint, PostgreSQL storing "
                "contact messages."
            ),
            "architecture": "Monolith",
            "components": [
                {"name": "Web UI", "description": "Next.js + Tailwind landing page"},
                {"name": "API", "description": "FastAPI contact message endpoint"},
                {"name": "Database", "description": "PostgreSQL contact message table"},
            ],
            "tech_stack": {
                "frontend": "Next.js 15, React, TypeScript, Tailwind CSS",
                "backend": "Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2",
                "database": "PostgreSQL 16",
                "auth": "none (public site)",
            },
        }
    },
    "lld": {
        "content": {
            "modules": [
                {
                    "name": "portfolio",
                    "description": "Landing page, projects showcase, and contact form",
                    "endpoints": [
                        {
                            "method": "POST",
                            "path": "/api/v1/contact",
                            "description": "Submit contact message",
                        },
                        {
                            "method": "GET",
                            "path": "/api/v1/contact",
                            "description": "List messages",
                        },
                    ],
                    "models": [
                        {
                            "name": "ContactMessage",
                            "fields": ["id", "name", "email", "message", "created_at"],
                        },
                    ],
                }
            ],
            "data_flow": "Frontend -> FastAPI -> PostgreSQL",
        }
    },
    "er_diagram": {
        "content": {
            "entities": [
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
            "relationships": [],
        }
    },
    "api_spec": {
        "content": {
            "base_url": "/api/v1",
            "authentication": "none (public site)",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/contact", "summary": "Submit contact message"},
                {"method": "GET", "path": "/api/v1/contact", "summary": "List messages"},
            ],
        }
    },
    "generated_schema": {
        "content": {
            "ddl": (
                "CREATE TABLE contact_message (\n"
                "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n"
                "  name VARCHAR(255) NOT NULL,\n"
                "  email VARCHAR(255) NOT NULL,\n"
                "  message TEXT NOT NULL,\n"
                "  created_at TIMESTAMPTZ DEFAULT NOW()\n"
                ");"
            )
        }
    },
    "wireframes": [
        {
            "content": {
                "title": "Portfolio",
                "screens": [
                    {
                        "name": "Landing Page",
                        "layout": "Single page scroll",
                        "components": [
                            "Hero section with name and tagline",
                            "Projects grid with cards",
                            "Contact form with name, email, message",
                        ],
                    }
                ],
            }
        }
    ],
    "bpmn_flows": [],
}


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
]

TEMPLATE_BY_SLUG: dict[str, MVPTemplate] = {t.slug: t for t in TEMPLATES}


def get_template(slug: str) -> MVPTemplate | None:
    return TEMPLATE_BY_SLUG.get(slug)


def list_templates() -> list[dict[str, str]]:
    return [t.to_dict() for t in TEMPLATES]
