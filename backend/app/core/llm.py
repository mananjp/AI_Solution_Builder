"""
AI Solution Builder — Pluggable LLM Provider Layer

Provides a single factory (`get_llm`) that resolves the configured
LLM_PROVIDER (groq | openai | mock) and returns a chat model with an
`ainvoke(messages)` method. When a provider API key is missing the
module falls back to the deterministic mock provider so development
and tests run without network access or credentials.

The mock provider inspects the system prompt to return valid,
node-specific JSON so the full LangGraph pipeline completes offline.
"""

import difflib
import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI

    _HAS_OPENAI = True
except ImportError:  # pragma: no cover
    _HAS_OPENAI = False


class MockMessage:
    """Duck-typed minimal result object matching the langchain Message API."""

    def __init__(self, content: str) -> None:
        self.content = content


def _mock_business_analyst() -> dict[str, Any]:
    return {
        "business_description": "Small business needing digital operations management across core functions.",
        "industry": "consulting_agency",
        "business_size": "sme",
        "business_stage": "growth",
        "stakeholders": ["owner", "ops_manager", "customers"],
        "pain_points": ["manual record keeping", "no central dashboard"],
        "identified_solutions": ["crm", "project_management"],
        "confidence_score": 0.9,
        "clarification_questions": [],
        "analysis_summary": "Analyzed the business: a consultancy needing CRM and project management systems.",
    }


def _mock_recommendation() -> dict[str, Any]:
    return {
        "industry": "consulting_agency",
        "recommended_modules": [
            {"module": "public_website", "reason": "Service showcase and lead generation"},
            {"module": "crm", "reason": "Client and prospect management"},
            {"module": "invoicing_billing", "reason": "Project billing and expense tracking"},
        ],
        "explanation": "Recommended core systems for a consulting agency.",
    }


def _mock_architecture() -> dict[str, Any]:
    return {
        "hld": {
            "title": "High-Level Design — Consultancy Platform",
            "system_overview": "A modular web platform with CRM and project management modules.",
            "components": [
                {"name": "web", "description": "Next.js frontend", "technology": "React"},
                {"name": "api", "description": "REST API", "technology": "FastAPI"},
                {"name": "db", "description": "PostgreSQL store", "technology": "PostgreSQL"},
            ],
            "integrations": [
                {"from": "web", "to": "api", "protocol": "REST", "description": "CRUD calls"}
            ],
            "deployment": {
                "environment": "cloud",
                "services": ["web", "api", "database"],
                "scaling_strategy": "horizontal",
            },
            "security": {
                "authentication": "JWT",
                "authorization": "RBAC",
                "encryption": "TLS + AES-256 at rest",
            },
        },
        "lld": {
            "title": "Low-Level Design — Consultancy Platform",
            "modules": [
                {
                    "name": "crm",
                    "description": "Customer relationship module",
                    "endpoints": [
                        {"method": "GET", "path": "/api/v1/crm/leads", "description": "List leads"}
                    ],
                    "data_models": ["leads", "clients", "deals"],
                },
                {
                    "name": "project_management",
                    "description": "Engagement tracking",
                    "endpoints": [
                        {
                            "method": "GET",
                            "path": "/api/v1/projects",
                            "description": "List projects",
                        }
                    ],
                    "data_models": ["projects", "tasks"],
                },
            ],
        },
    }


def _mock_ux() -> dict[str, Any]:
    return {
        "wireframes": [
            {
                "module": "crm",
                "screens": [
                    {
                        "name": "Leads Dashboard",
                        "route": "/crm/leads",
                        "description": "Overview of leads",
                        "layout": "sidebar",
                        "components": [
                            {
                                "type": "data_table",
                                "title": "Leads Table",
                                "description": "Rows of leads",
                                "fields": ["name", "company", "status"],
                            }
                        ],
                    }
                ],
            }
        ],
        "navigation": {
            "primary_menu": [{"label": "Leads", "icon": "users", "route": "/crm/leads"}],
            "user_flows": [
                {"name": "Convert Lead", "steps": ["Open lead", "Update status", "Create deal"]}
            ],
        },
        "design_tokens": {
            "primary_color": "#4f46e5",
            "secondary_color": "#0891b2",
            "font_family": "Inter",
            "border_radius": "8px",
        },
    }


_MOCK_OPERATIONAL_DDL = (
    "CREATE TABLE clients (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "name VARCHAR(255) NOT NULL);"
    "\nCREATE TABLE leads (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "name VARCHAR(255) NOT NULL, company VARCHAR(255), "
    "status VARCHAR(50) NOT NULL DEFAULT 'new');"
    "\nCREATE TABLE projects (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "client_id UUID NOT NULL REFERENCES clients(id), name VARCHAR(255) NOT NULL);"
)


def _mock_database() -> dict[str, Any]:
    entities = [
        {
            "name": "leads",
            "fields": [
                {
                    "name": "id",
                    "type": "UUID",
                    "primary_key": True,
                    "nullable": False,
                    "foreign_key": None,
                },
                {
                    "name": "name",
                    "type": "VARCHAR(255)",
                    "primary_key": False,
                    "nullable": False,
                    "foreign_key": None,
                },
                {
                    "name": "company",
                    "type": "VARCHAR(255)",
                    "primary_key": False,
                    "nullable": True,
                    "foreign_key": None,
                },
                {
                    "name": "status",
                    "type": "VARCHAR(50)",
                    "primary_key": False,
                    "nullable": False,
                    "foreign_key": None,
                },
            ],
        },
        {
            "name": "projects",
            "fields": [
                {
                    "name": "id",
                    "type": "UUID",
                    "primary_key": True,
                    "nullable": False,
                    "foreign_key": None,
                },
                {
                    "name": "client_id",
                    "type": "UUID",
                    "primary_key": False,
                    "nullable": False,
                    "foreign_key": "clients.id",
                },
                {
                    "name": "name",
                    "type": "VARCHAR(255)",
                    "primary_key": False,
                    "nullable": False,
                    "foreign_key": None,
                },
            ],
        },
    ]
    ddl = _MOCK_OPERATIONAL_DDL
    return {
        "er_diagram": {
            "entities": entities,
            "relationships": [
                {"from": "projects", "to": "clients", "type": "many-to-one", "via": None}
            ],
        },
        "schema_ddl": ddl,
        "api_endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/leads",
                "description": "List leads",
                "request_body": None,
                "response": {"items": "array"},
            },
            {
                "method": "POST",
                "path": "/api/v1/leads",
                "description": "Create lead",
                "request_body": {"name": "string"},
                "response": {"id": "uuid"},
            },
            {
                "method": "GET",
                "path": "/api/v1/projects",
                "description": "List projects",
                "request_body": None,
                "response": {"items": "array"},
            },
        ],
    }


def _mock_process_intelligence(state: dict[str, Any]) -> dict[str, Any]:
    modules = (
        state.get("identified_solutions")
        or state.get("confirmed_modules")
        or ["crm", "project_management"]
    )
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_id = "start"
    nodes.append(
        {"id": node_id, "type": "start", "position": {"x": 0, "y": 100}, "data": {"label": "Start"}}
    )
    prev = node_id
    for i, module in enumerate(modules):
        current = f"task_{i}"
        nodes.append(
            {
                "id": current,
                "type": "task",
                "position": {"x": 200 + i * 220, "y": 100},
                "data": {"label": f"{module} workflow"},
            }
        )
        edges.append({"id": f"e{prev}_{current}", "source": prev, "target": current})
        prev = current
    nodes.append(
        {
            "id": "end",
            "type": "end",
            "position": {"x": 200 + len(modules) * 220, "y": 100},
            "data": {"label": "End"},
        }
    )
    edges.append({"id": f"e{prev}_end", "source": prev, "target": "end"})

    return {
        "bpmn": {
            "name": "Core Business Process",
            "xml": '<?xml version="1.0" encoding="UTF-8"?>\n<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:process id="Process_1" isExecutable="true"/></bpmn:definitions>',
            "flows": [{"id": "flow_1", "name": "End-to-end delivery"}],
        },
        "react_flow": {"nodes": nodes, "edges": edges},
        "swimlanes": [
            {
                "id": "lane_ops",
                "label": "Operations",
                "tasks": [t["id"] for t in nodes if t["type"] == "task"],
            }
        ],
        "bottlenecks": [
            {
                "module": modules[0] if modules else "crm",
                "severity": "low",
                "reason": "Manual status updates may throttle throughput",
            }
        ],
    }


def _mock_code() -> dict[str, Any]:
    return {
        "generated_schema": {
            "tables": [
                {"table": "leads", "columns": ["id UUID", "name VARCHAR", "status VARCHAR"]},
                {"table": "projects", "columns": ["id UUID", "client_id UUID", "name VARCHAR"]},
            ],
            "ddl": _MOCK_OPERATIONAL_DDL,
        },
        "workable_modules": [
            {
                "module": "crm",
                "path": "/crm",
                "entities": ["leads"],
                "summary": "Lead management: list, create, update, delete.",
            },
            {
                "module": "project_management",
                "path": "/projects",
                "entities": ["projects"],
                "summary": "Project tracking with task lists.",
            },
        ],
        "code_manifest": {
            "framework": "FastAPI + Next.js",
            "tree": [
                "backend/app.py",
                "backend/models.py",
                "frontend/pages/leads.tsx",
                "frontend/pages/projects.tsx",
            ],
            "stack_version": "2026.1",
        },
    }


def _mock_blueprint() -> dict[str, Any]:
    return {
        "executive_summary": "A modular CRM and project management platform for consultancies.",
        "roadmap": {
            "phases": [
                {
                    "name": "Foundation",
                    "duration": "2 weeks",
                    "modules": ["crm"],
                    "milestones": ["Working lead CRUD"],
                    "deliverables": ["Database", "REST API", "UI"],
                }
            ],
            "total_duration": "8 weeks",
        },
        "effort_estimation": [
            {"module": "crm", "effort_days": 10, "complexity": "medium"},
            {"module": "project_management", "effort_days": 8, "complexity": "medium"},
        ],
        "risks": [{"risk": "Scope creep", "impact": "medium", "mitigation": "Agile iterations"}],
        "success_metrics": [
            {
                "metric": "Time-to-first-deal",
                "target": "<7 days",
                "measurement_method": "CRM funnel",
            }
        ],
        "next_steps": ["Provision schema", "Start sprint 1"],
    }


def _normalize_domain_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# Shared domain knowledge base used by the mock AI Developer (prose reply) and
# the mock AppSpec generator (build synthesis). Matches are fuzzy on the user's
# raw text, so misspellings like "e-commerse" still map to e-commerce.
_DOMAINS: list[dict[str, Any]] = [
    {
        "keywords": (
            "agent",
            "bot",
            "assistant",
            "copilot",
            "llm",
            "autonomous",
            "orchestrator",
            "rag",
            "prompt",
            "workspace",
            "synthesis",
            "architect",
        ),
        "app_type": "Autonomous AI Agent Workspace",
        "entities": ["Agents", "Tools", "Conversations", "Messages", "Executions"],
        "spec_entities": [
            ("agent", "agents"),
            ("tool", "tools"),
            ("conversation", "conversations"),
            ("workspace", "workspaces"),
        ],
        "endpoints": [
            "/api/v1/agents",
            "/api/v1/agents/{id}/run",
            "/api/v1/tools",
            "/api/v1/conversations",
            "/api/v1/executions",
        ],
    },
    {
        "keywords": (
            "commerce",
            "commerse",
            "store",
            "shop",
            "retail",
            "product",
            "inventory",
            "cart",
            "checkout",
            "order",
            "sell",
            "buy",
            "payment",
        ),
        "app_type": "E-Commerce & Storefront Platform",
        "entities": ["Products", "Orders", "Customers", "Categories", "Cart Items"],
        "spec_entities": [
            ("product", "products"),
            ("category", "categories"),
            ("order", "orders"),
            ("customer", "customers"),
        ],
        "endpoints": [
            "/api/v1/products",
            "/api/v1/products/{id}",
            "/api/v1/orders",
            "/api/v1/customers",
            "/api/v1/cart",
        ],
    },
    {
        "keywords": (
            "health",
            "clinic",
            "doctor",
            "patient",
            "medical",
            "telehealth",
            "ehr",
            "hospital",
        ),
        "app_type": "Healthcare & Clinic Management System",
        "entities": ["Patients", "Doctors", "Appointments", "Prescriptions", "Departments"],
        "spec_entities": [
            ("patient", "patients"),
            ("physician", "physicians"),
            ("appointment", "appointments"),
            ("treatment", "treatments"),
        ],
        "endpoints": [
            "/api/v1/patients",
            "/api/v1/appointments",
            "/api/v1/physicians",
            "/api/v1/records",
        ],
    },
    {
        "keywords": (
            "logistics",
            "fleet",
            "dispatch",
            "driver",
            "freight",
            "truck",
            "shipment",
            "courier",
        ),
        "app_type": "Logistics & Fleet Dispatch Platform",
        "entities": ["Shipments", "Vehicles", "Drivers", "Routes", "Deliveries"],
        "spec_entities": [
            ("shipment", "shipments"),
            ("vehicle", "vehicles"),
            ("driver", "drivers"),
            ("route", "routes"),
        ],
        "endpoints": [
            "/api/v1/shipments",
            "/api/v1/routes",
            "/api/v1/drivers",
            "/api/v1/deliveries",
        ],
    },
    {
        "keywords": ("crm", "lead", "client", "sales", "deal", "pipeline", "prospect"),
        "app_type": "CRM & Sales Pipeline Platform",
        "entities": ["Leads", "Contacts", "Deals", "Activities", "Pipelines"],
        "spec_entities": [
            ("lead", "leads"),
            ("contact", "contacts"),
            ("deal", "deals"),
            ("activity", "activities"),
        ],
        "endpoints": ["/api/v1/leads", "/api/v1/clients", "/api/v1/deals", "/api/v1/activities"],
    },
    {
        "keywords": ("todo", "task", "project", "kanban", "sprint", "trello", "issue", "jira"),
        "app_type": "Project & Task Management System",
        "entities": ["Projects", "Tasks", "Milestones", "Tags", "Boards"],
        "spec_entities": [
            ("project", "projects"),
            ("task", "tasks"),
            ("sprint", "sprints"),
            ("milestone", "milestones"),
        ],
        "endpoints": ["/api/v1/projects", "/api/v1/tasks", "/api/v1/boards"],
    },
    {
        "keywords": (
            "finance",
            "invoice",
            "billing",
            "expense",
            "accounting",
            "bookkeeping",
            "revenue",
        ),
        "app_type": "Finance & Invoicing Platform",
        "entities": ["Invoices", "Transactions", "Expenses", "Accounts", "Clients"],
        "spec_entities": [
            ("invoice", "invoices"),
            ("expense", "expenses"),
            ("customer", "customers"),
            ("payment", "payments"),
        ],
        "endpoints": [
            "/api/v1/invoices",
            "/api/v1/transactions",
            "/api/v1/expenses",
            "/api/v1/accounts",
        ],
    },
    {
        "keywords": ("property", "realestate", "listing", "tenant", "rental", "realtor", "lease"),
        "app_type": "Real Estate & Property Management",
        "entities": ["Properties", "Listings", "Leases", "Tenants", "Showings"],
        "spec_entities": [
            ("property", "properties"),
            ("listing", "listings"),
            ("tenant", "tenants"),
            ("showing", "showings"),
        ],
        "endpoints": ["/api/v1/properties", "/api/v1/listings", "/api/v1/leases"],
    },
    {
        "keywords": ("course", "student", "teacher", "learning", "lms", "classroom", "lesson"),
        "app_type": "Education & Learning Management System",
        "entities": ["Courses", "Lessons", "Students", "Enrollments", "Instructors"],
        "spec_entities": [
            ("course", "courses"),
            ("student", "students"),
            ("enrollment", "enrollments"),
            ("lesson", "lessons"),
        ],
        "endpoints": ["/api/v1/courses", "/api/v1/lessons", "/api/v1/students"],
    },
    {
        "keywords": ("member", "class", "fitness", "gym", "coach", "wellness", "workout"),
        "app_type": "Fitness & Wellness Club Platform",
        "entities": ["Members", "Classes", "Trainers", "Bookings", "Plans"],
        "spec_entities": [
            ("member", "members"),
            ("class", "classes"),
            ("trainer", "trainers"),
            ("booking", "bookings"),
        ],
        "endpoints": ["/api/v1/members", "/api/v1/classes", "/api/v1/bookings"],
    },
    {
        "keywords": (
            "restaurant",
            "menu",
            "dish",
            "reservation",
            "chef",
            "catering",
            "kitchen",
        ),
        "app_type": "Restaurant & Kitchen Management",
        "entities": ["Dishes", "Menu Items", "Reservations", "Orders", "Ingredients"],
        "spec_entities": [
            ("menu_item", "menu_items"),
            ("dish", "dishes"),
            ("reservation", "reservations"),
            ("ingredient", "ingredients"),
        ],
        "endpoints": ["/api/v1/menu-items", "/api/v1/reservations", "/api/v1/orders"],
    },
    {
        "keywords": (
            "movie",
            "event",
            "ticket",
            "venue",
            "show",
            "concert",
            "booking",
            "festival",
        ),
        "app_type": "Events & Ticketing Platform",
        "entities": ["Events", "Tickets", "Attendees", "Venues", "Orders"],
        "spec_entities": [
            ("event", "events"),
            ("ticket", "tickets"),
            ("attendee", "attendees"),
            ("venue", "venues"),
        ],
        "endpoints": ["/api/v1/events", "/api/v1/tickets", "/api/v1/venues"],
    },
    {
        "keywords": ("employee", "candidate", "applicant", "hiring", "onboarding", "timesheet"),
        "app_type": "HR & Workforce Management",
        "entities": ["Employees", "Candidates", "Job Posts", "Reviews", "Leave Requests"],
        "spec_entities": [
            ("employee", "employees"),
            ("candidate", "candidates"),
            ("job_post", "job_posts"),
            ("review", "reviews"),
        ],
        "endpoints": ["/api/v1/employees", "/api/v1/candidates", "/api/v1/job-posts"],
    },
    {
        "keywords": [],
        "app_type": "Full-Stack Web Application",
        "entities": ["Users", "Records", "Categories", "Activities"],
        "spec_entities": [("item", "items"), ("category", "categories")],
        "endpoints": ["/api/v1/items", "/api/v1/categories", "/api/v1/users"],
    },
]


# English idioms whose words collide with domain keywords. "in order to" is
# extremely common in LLM-generated prose, and its bare "order" token otherwise
# scores an exact hit for the e-commerce domain. That silently hijacked
# unrelated requests - "manage your employees in order to track leave" was
# detected as E-Commerce and built products/orders - so these phrases are
# stripped before tokenizing.
_DOMAIN_IDIOMS: tuple[str, ...] = (
    "in order to",
    "in order for",
    "in order of",
    "in order that",
    "order of",
    "sort of",
    "kind of",
)

# Domain keywords that are also ordinary English/business words. They stay
# usable, but an exact hit is worth less than a real domain noun, so filler
# prose cannot outrank the actual subject of the request.
_AMBIGUOUS_DOMAIN_KEYWORDS: frozenset[str] = frozenset(
    {
        "order",
        "orders",
        "class",
        "classes",
        "member",
        "members",
        "record",
        "records",
        "service",
        "services",
        "staff",
        "team",
        "group",
        "groups",
        "type",
        "card",
        "cards",
        "board",
        "report",
    }
)
_AMBIGUOUS_KEYWORD_PENALTY = 0.55


def _detect_domain(user_text: str) -> dict[str, Any]:
    """Pick the domain that best matches *user_text* (fuzzy, misspelling-tolerant).

    Exact keyword matches win; otherwise the best normalized fuzzy match wins;
    otherwise the generic fallback domain is returned.
    """
    normalized = user_text.lower()
    for idiom in _DOMAIN_IDIOMS:
        normalized = normalized.replace(idiom, " ")
    tokens = [t for t in re.findall(r"[a-z0-9]+", normalized) if len(t) >= 2]

    def _score_keyword(kw_norm: str) -> float:
        best = -1.0
        for tok in tokens:
            if kw_norm == tok:
                best = max(best, 2.0)
            elif kw_norm in tok:
                # Near-exact: a plural like "employees" must not lose to an
                # unrelated word that happens to be an exact token match.
                best = max(best, 1.9)
            elif len(kw_norm) >= 4 and difflib.SequenceMatcher(None, kw_norm, tok).ratio() >= 0.8:
                best = max(best, 1.0)
        if best > 0.0 and kw_norm in _AMBIGUOUS_DOMAIN_KEYWORDS:
            best *= _AMBIGUOUS_KEYWORD_PENALTY
        return best

    best_domain: dict[str, Any] | None = None
    best_score = -1.0
    for dom in _DOMAINS[:-1]:
        for kw in dom["keywords"]:
            kw_norm = _normalize_domain_text(kw)
            if not kw_norm:
                continue
            score = _score_keyword(kw_norm)
            if score > best_score:
                best_score = score
                best_domain = dom
    if best_domain is not None and best_score > 0.0:
        return best_domain
    return _DOMAINS[-1]


def _mock_ai_developer(messages: list[Any]) -> dict[str, Any]:
    user_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_text = str(getattr(msg, "content", ""))

    domain = _detect_domain(user_text)
    app_type = domain["app_type"]
    entities = domain["entities"]
    endpoints = domain["endpoints"]

    ent_bullets = "\n".join(
        f"- **{e}**: UUID identifier, status tracking, timestamps, and relationship mapping."
        for e in entities
    )
    ep_bullets = "\n".join(
        f"- `GET {ep}` & `POST {ep}` — List, filter, and create records with validation."
        for ep in endpoints
    )

    content = (
        f"I have architected a tailored **{app_type}** solution for your requirements.\n\n"
        f"### 1. Data Models & Database\n{ent_bullets}\n\n"
        f"### 2. REST API Endpoints (FastAPI)\n{ep_bullets}\n\n"
        f"### 3. Next.js Frontend Pages\n"
        f"- **Dashboard & Data Tables**: Real-time management interface with search, sorting, and pagination.\n"
        f"- **Action Modals**: Record creation, editing, and status updates.\n\n"
        f"The workspace is configured with database models, schemas, routers, and deployment configs. "
        f"Toggle **Build** and send to verify and finalize your deployable package!"
    )
    return {"content": content}


_MOCK_SPEC_MARKER = "You design rich, production-grade working apps"  # app_spec.SPEC_SYSTEM

# Verbs that mark a phrase as a product name rather than a sentence, used when
# deriving a title from a free-text request ("build me an Employee Management
# System" -> "Employee Management System").
_APP_NAME_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "app",
        "application",
        "build",
        "building",
        "create",
        "design",
        "for",
        "generate",
        "i",
        "in",
        "make",
        "me",
        "my",
        "need",
        "of",
        "please",
        "simple",
        "small",
        "system",
        "that",
        "the",
        "this",
        "to",
        "want",
        "website",
        "with",
    }
)


def _derive_app_name(user_text: str) -> str:
    """Best-effort product name from a free-text request.

    The offline agent used to hardcode "My App", so every offline build was
    titled "My App" regardless of the request. Prefer an explicit
    "<X> system/app/platform" phrase, then a capitalised phrase, then give up.
    """
    text = re.sub(r"\s+", " ", user_text).strip()
    if not text:
        return ""

    m = re.search(
        r"\b((?:[A-Za-z][\w&+.-]*\s+){0,4}?"
        r"(?:system|app|application|platform|dashboard|portal|tracker|manager))\b",
        text,
        re.IGNORECASE,
    )
    if m:
        # Strip only LEADING request verbs/articles so the title is the product,
        # not the sentence: "Build an Employee Management System" -> "Employee
        # Management System", "I need a todo app" -> "Todo App". The trailing
        # head noun (System/App/Platform) is part of the name and is kept.
        words = re.findall(r"[A-Za-z][\w&+.-]*", m.group(1))
        while words and words[0].lower() in _APP_NAME_STOPWORDS:
            words.pop(0)
        if words:
            candidate = " ".join(words)
            return candidate[:1].upper() + candidate[1:]

    # Fall back to the first meaningful words. A bare acronym is a good name on
    # its own ("CRM"), so do not pad it with the words that followed it.
    all_words: list[str] = re.findall(r"[A-Za-z][\w&+.-]*", text)
    meaningful: list[str] = [w for w in all_words if w.lower() not in _APP_NAME_STOPWORDS]
    if meaningful:
        first: str = meaningful[0]
        if first.isupper() and 2 <= len(first) <= 5:
            return first
        return " ".join(meaningful[:3])[:60]
    return ""


def _mock_domain_actions(entities: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Generic domain actions so an offline build is not bare CRUD.

    The offline agent emitted `"actions": []`, which produced a pure
    record-listing app with no business logic. These are deliberately generic
    and derived from whatever entities were detected, so they stay correct for
    any domain instead of hardcoding one industry's rules.
    """
    if len(entities) < 2:
        return []
    (primary, primary_plural) = entities[0]
    (related, related_plural) = entities[1]
    return [
        {
            "name": f"{related}_summary",
            "method": "GET",
            "path": f"/actions/{related_plural}/summary",
            "summary": f"Aggregate {primary_plural} grouped by {related}.",
            "input_fields": [],
            "rules": [
                f"Group all {primary_plural} by their {related} reference.",
                f'Return an object keyed by {related} name; each value is '
                f'{{"total": <int count of {primary_plural}>, "names": [<{primary} name>]}}.',
                "Return an empty object when there is no data.",
                f"Return 404 if the {related} does not exist.",
            ],
            "output_example": {},
        },
        {
            "name": f"create_{primary}_for_{related}",
            "method": "POST",
            "path": f"/actions/{primary_plural}",
            "summary": f"Create a {primary} that must reference an existing {related}.",
            "input_fields": [
                {
                    "name": f"{related}_id",
                    "type": "int",
                    "required": True,
                    "description": f"Existing {related}",
                }
            ],
            "rules": [
                f"Look up {related} by {related}_id; return 400 if it does not exist.",
                f"Return 404 if {related}_id is not a valid integer.",
                f"Return 409 if a {primary} with the same natural key already exists for that {related}.",
                f"Otherwise create the {primary}, attach {related}_id, "
                f'return the created object including "id".',
            ],
            "output_example": {},
        },
    ]


def _mock_app_spec(messages: list[Any]) -> dict[str, Any]:
    """Deterministic valid AppSpec JSON for offline/mock mode (no keyword templates).

    Picks entities from the user text only to give the spec relevance; it never
    substitutes canned domain templates the way the legacy heuristic did.
    """
    user_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_text += "\n" + str(getattr(msg, "content", ""))

    domain = _detect_domain(user_text)
    entities = domain["spec_entities"]

    _FIELD_SETS: dict[str, list[dict[str, Any]]] = {
        "product": [
            {"name": "name", "type": "string", "required": True, "description": "Product name"},
            {"name": "price", "type": "float", "required": True, "description": "Sale price"},
            {"name": "stock_quantity", "type": "int", "required": False, "description": "Units on hand"},
            {"name": "is_active", "type": "bool", "required": False, "description": "Visible in storefront"},
        ],
        "order": [
            {"name": "order_number", "type": "string", "required": True, "description": "Public order reference"},
            {"name": "customer_email", "type": "string", "required": True, "description": "Buyer email"},
            {"name": "total_amount", "type": "float", "required": True, "description": "Order total"},
            {"name": "status", "type": "string", "required": False, "description": "Order lifecycle status"},
        ],
        "customer": [
            {"name": "full_name", "type": "string", "required": True, "description": "Customer name"},
            {"name": "email", "type": "string", "required": True, "description": "Contact email"},
            {"name": "phone", "type": "string", "required": False, "description": "Contact phone"},
            {"name": "city", "type": "string", "required": False, "description": "Billing city"},
        ],
        "category": [
            {"name": "name", "type": "string", "required": True, "description": "Category name"},
            {"name": "slug", "type": "string", "required": False, "description": "URL-friendly identifier"},
        ],
        "patient": [
            {"name": "full_name", "type": "string", "required": True, "description": "Patient name"},
            {"name": "email", "type": "string", "required": True, "description": "Contact email"},
            {"name": "date_of_birth", "type": "date", "required": False, "description": "Date of birth"},
            {"name": "blood_group", "type": "string", "required": False, "description": "ABO group"},
        ],
        "appointment": [
            {"name": "scheduled_at", "type": "datetime", "required": True, "description": "Appointment time"},
            {"name": "status", "type": "string", "required": False, "description": "Status"},
            {"name": "reason", "type": "text", "required": False, "description": "Visit reason"},
        ],
        "invoice": [
            {"name": "invoice_number", "type": "string", "required": True, "description": "Invoice reference"},
            {"name": "client_name", "type": "string", "required": True, "description": "Billed party"},
            {"name": "amount_due", "type": "float", "required": True, "description": "Amount owed"},
            {"name": "due_date", "type": "date", "required": False, "description": "Payment due date"},
            {"name": "status", "type": "string", "required": False, "description": "Billing status"},
        ],
        "shipment": [
            {"name": "tracking_number", "type": "string", "required": True, "description": "Courier tracking"},
            {"name": "status", "type": "string", "required": False, "description": "Delivery status"},
            {"name": "destination_city", "type": "string", "required": False, "description": "Destination"},
            {"name": "estimated_delivery", "type": "date", "required": False, "description": "ETA"},
        ],
        "event": [
            {"name": "title", "type": "string", "required": True, "description": "Event title"},
            {"name": "starts_at", "type": "datetime", "required": True, "description": "Start time"},
            {"name": "venue", "type": "string", "required": False, "description": "Venue name"},
            {"name": "capacity", "type": "int", "required": False, "description": "Seat capacity"},
        ],
        "ticket": [
            {"name": "holder_name", "type": "string", "required": True, "description": "Ticket holder"},
            {"name": "price", "type": "float", "required": True, "description": "Ticket price"},
            {"name": "status", "type": "string", "required": False, "description": "Booking status"},
        ],
        "task": [
            {"name": "title", "type": "string", "required": True, "description": "Task title"},
            {"name": "due_date", "type": "date", "required": False, "description": "Due date"},
            {"name": "priority", "type": "string", "required": False, "description": "Priority level"},
            {"name": "completed", "type": "bool", "required": False, "description": "Done flag"},
        ],
        "project": [
            {"name": "name", "type": "string", "required": True, "description": "Project name"},
            {"name": "description", "type": "text", "required": False, "description": "Notes"},
            {"name": "start_date", "type": "date", "required": False, "description": "Start date"},
            {"name": "status", "type": "string", "required": False, "description": "Project status"},
        ],
        "member": [
            {"name": "full_name", "type": "string", "required": True, "description": "Member name"},
            {"name": "email", "type": "string", "required": True, "description": "Contact email"},
            {"name": "plan_name", "type": "string", "required": False, "description": "Membership plan"},
            {"name": "joined_at", "type": "date", "required": False, "description": "Join date"},
        ],
        "course": [
            {"name": "title", "type": "string", "required": True, "description": "Course title"},
            {"name": "description", "type": "text", "required": False, "description": "Course details"},
            {"name": "price", "type": "float", "required": False, "description": "Tuition price"},
        ],
        "lead": [
            {"name": "full_name", "type": "string", "required": True, "description": "Lead name"},
            {"name": "email", "type": "string", "required": True, "description": "Contact email"},
            {"name": "status", "type": "string", "required": False, "description": "Pipeline stage"},
            {"name": "deal_value", "type": "float", "required": False, "description": "Opportunity value"},
        ],
        "candidate": [
            {"name": "full_name", "type": "string", "required": True, "description": "Candidate name"},
            {"name": "email", "type": "string", "required": True, "description": "Contact email"},
            {"name": "status", "type": "string", "required": False, "description": "Hiring stage"},
        ],
        "menu_item": [
            {"name": "name", "type": "string", "required": True, "description": "Dish name"},
            {"name": "price", "type": "float", "required": True, "description": "Selling price"},
            {"name": "is_available", "type": "bool", "required": False, "description": "On menu"},
        ],
        "employee": [
            {"name": "full_name", "type": "string", "required": True, "description": "Employee name"},
            {"name": "email", "type": "string", "required": True, "description": "Work email"},
            {"name": "department", "type": "string", "required": False, "description": "Department"},
            {"name": "hire_date", "type": "date", "required": False, "description": "Hire date"},
        ],
        "property": [
            {"name": "address", "type": "string", "required": True, "description": "Property address"},
            {"name": "price", "type": "float", "required": True, "description": "Listing price"},
            {"name": "status", "type": "string", "required": False, "description": "Listing status"},
        ],
    }

    def _fields_for(name: str) -> list[dict[str, Any]]:
        return _FIELD_SETS.get(name) or [
            {"name": "name", "type": "string", "required": True, "description": "Display name"},
            {"name": "description", "type": "text", "required": False, "description": "Notes"},
        ]

    spec_entities = [
        {
            "name": name,
            "plural": plural,
            "description": f"{name} managed by the app",
            "fields": _fields_for(name),
        }
        for name, plural in entities
    ]

    domain_actions = _mock_domain_actions(entities)
    action_names = [a["name"] for a in domain_actions]
    screens = [
        {
            "name": "dashboard",
            "route": "/",
            "purpose": "Overview of managed records",
            "uses_entities": [name for name, _ in entities],
            "uses_actions": action_names,
            "key_interactions": ["view records", "view summary"],
        },
        *[
            {
                "name": f"{name}_management",
                "route": f"/{plural}",
                "purpose": f"Manage {plural}",
                "uses_entities": [name],
                "uses_actions": [a for a in action_names if name in a],
                "key_interactions": ["create record", "edit record", "delete record"],
            }
            for name, plural in entities
        ],
    ]

    first_plural = entities[0][1]
    acceptance_tests = [
        {
            "name": "create_record",
            "description": "A record can be created",
            "steps": [
                {
                    "method": "POST",
                    "path": f"/{first_plural}",
                    "body": {"name": "Sample"},
                    "expect_status": 201,
                    "expect": {"name": "Sample"},
                    "save": {"id": "id"},
                }
            ],
        },
        {
            "name": "list_records",
            "description": "Records are listed",
            "steps": [
                {
                    "method": "GET",
                    "path": f"/{first_plural}",
                    "expect_status": 200,
                    "expect": {},
                    "save": {},
                }
            ],
        },
        {
            "name": "get_record",
            "description": "A single record can be fetched",
            "steps": [
                {
                    "method": "POST",
                    "path": f"/{first_plural}",
                    "body": {"name": "Another"},
                    "expect_status": 201,
                    "expect": {},
                    "save": {"id": "id"},
                },
                {
                    "method": "GET",
                    "path": f"/{first_plural}/{{id}}",
                    "expect_status": 200,
                    "expect": {},
                    "save": {},
                },
            ],
        },
    ]

    return {
        "app_name": _derive_app_name(user_text) or domain["app_type"],
        "one_liner": f"A {domain['app_type']} based on your request",
        "core_value": (
            f"Tracks {', '.join(plural for _, plural in entities)} with domain rules, "
            f"cross-entity validation and aggregate reporting, rather than plain record CRUD."
        ),
        "assumptions": [],
        "entities": spec_entities,
        "actions": _mock_domain_actions(entities),
        "screens": screens,
        "acceptance_tests": acceptance_tests,
    }


def _mock_requirement_gap() -> dict[str, Any]:
    """Deterministic gap-analysis payload (matches requirement_gap_node's contract)."""
    return {
        "requirements": [
            {
                "id": "req-nfr-1",
                "kind": "nfr",
                "text": "Role-based access control (RBAC) and audit trail logging",
                "status": "missing",
                "priority": "must",
                "evidence": [{"source": "mock", "excerpt": "Enterprise baseline checklist"}],
            },
            {
                "id": "req-comp-1",
                "kind": "compliance",
                "text": "Data protection, consent management, and data residency (DPDP/GDPR)",
                "status": "missing",
                "priority": "must",
                "evidence": [{"source": "mock", "excerpt": "Compliance checklist"}],
            },
            {
                "id": "req-arch-1",
                "kind": "integration",
                "text": "Multi-channel notifications (SMS / Email / WhatsApp)",
                "status": "suggested",
                "priority": "should",
                "evidence": [{"source": "mock", "excerpt": "Architecture gap analysis"}],
            },
            {
                "id": "req-arch-2",
                "kind": "functional",
                "text": "Payment reconciliation for refunds and failed transactions",
                "status": "suggested",
                "priority": "should",
                "evidence": [{"source": "mock", "excerpt": "Payments reconciliation checklist"}],
            },
        ],
        "open_questions": [
            {
                "id": "q-comp-1",
                "question": "Which customer data privacy and regulatory standards (e.g. DPDP, GDPR, HIPAA) apply to your users?",
                "category": "compliance",
                "why_it_matters": "Determines encryption-at-rest, consent capture flows, and data residency architecture.",
                "suggested_answers": [
                    "DPDP Act (India)",
                    "GDPR (Europe)",
                    "Standard commercial privacy",
                ],
            },
            {
                "id": "q-scale-1",
                "question": "What is the expected concurrent user load and availability SLA?",
                "category": "scale",
                "why_it_matters": "Drives auto-scaling, caching, and backup/recovery design decisions.",
                "suggested_answers": [
                    "Internal team (<50 users)",
                    "100-1,000 users",
                    "10,000+ users",
                ],
            },
        ],
        "assumptions_log": [
            {
                "id": "asm-sec-1",
                "topic": "security",
                "assumption": "Assumed multi-tenant data isolation with RBAC enforcement",
                "impact": "high",
            }
        ],
    }


def _mock_feature_advisor() -> dict[str, Any]:
    """Deterministic feature-advisor payload (matches feature_advisor_node's contract)."""
    return {
        "suggested_features": [
            {
                "id": "feat-notify-1",
                "name": "Automated Multi-Channel Notifications",
                "description": "SMS, Email, and WhatsApp status notifications with retry policies",
                "competitive_benchmark": "Leading platforms provide real-time order and status alerts",
                "roi_rationale": "Reduces no-show and missed-action rates by up to 25%",
                "complexity": "low",
                "category": "experience",
            },
            {
                "id": "feat-report-1",
                "name": "Executive Insight Dashboard",
                "description": "Role-scoped KPIs with scheduled PDF/email exports",
                "competitive_benchmark": "Standard for mid-market SaaS admin consoles",
                "roi_rationale": "Saves ~4h/week of manual reporting and improves decision velocity",
                "complexity": "medium",
                "category": "automation",
            },
            {
                "id": "feat-recon-1",
                "name": "Payments Reconciliation Ledger",
                "description": "Automated matching of gateway webhooks, refunds, and settlement reports",
                "competitive_benchmark": "Distinguishes finance-grade platforms from simple storefronts",
                "roi_rationale": "Eliminates manual reconciliation, cutting errors and days of close time",
                "complexity": "medium",
                "category": "automation",
            },
        ]
    }


def _build_mock_content(messages: list[Any], state: dict[str, Any]) -> str:
    """Return node-appropriate JSON based on the system prompt marker."""
    system_text = ""
    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_text = str(msg.content)

    if _MOCK_SPEC_MARKER in system_text:
        return json.dumps(_mock_app_spec(messages), indent=2)
    if (
        "full-stack AI Developer" in system_text
        or "Custom App Builder" in system_text
        or "AI Developer" in system_text
    ):
        payload = _mock_ai_developer(messages)
    elif "Business Analyst Agent" in system_text:
        payload = _mock_business_analyst()
    elif "Business Recommendation Agent" in system_text:
        payload = _mock_recommendation()
    elif "Solutions Architect Agent" in system_text:
        payload = _mock_architecture()
    elif "UX Designer Agent" in system_text:
        payload = _mock_ux()
    elif "Database & API Designer Agent" in system_text:
        payload = _mock_database()
    elif "Process Intelligence" in system_text:
        payload = _mock_process_intelligence(state)
    elif "Enterprise Solutions Analyst" in system_text:
        payload = _mock_requirement_gap()
    elif "Product Strategy and ROI Advisor" in system_text:
        payload = _mock_feature_advisor()
    elif "Full-Stack Code Synthesizer" in system_text:
        payload = _mock_code()
    elif "Blueprint Generator Agent" in system_text:
        payload = _mock_blueprint()
    else:
        payload = {"content": "Mock response"}

    return json.dumps(payload, indent=2)


class MockChatModel:
    """Deterministic chat model that returns valid per-agent JSON."""

    model: str = "mock"

    def __init__(self, **kwargs: Any) -> None:
        self.temperature = kwargs.get("temperature", 0.3)
        self.max_tokens = kwargs.get("max_tokens", 2048)
        self.state: dict[str, Any] = kwargs.get("state", {})

    async def ainvoke(self, messages: list[Any]) -> MockMessage:
        content = _build_mock_content(messages, self.state)
        logger.debug("MockLLM returned %d characters", len(content))
        return MockMessage(content)


def get_llm(**kwargs: Any) -> Any:
    """Resolve the configured LLM provider.

    Accepts temperature/max_tokens overrides. Falls back to the mock provider
    when the configured provider has no API key (dev/test convenience).
    """
    provider = settings.LLM_PROVIDER.lower()

    # The mock provider uses `state` to build process/code payloads; strip it
    # from the kwargs forwarded to real providers.
    state = kwargs.pop("state", {})

    if provider == "groq" and settings.GROQ_API_KEY:
        return ChatGroq(
            api_key=SecretStr(settings.GROQ_API_KEY),
            model=settings.GROQ_MODEL_NAME,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

    if provider == "openai" and _HAS_OPENAI and settings.OPENAI_API_KEY:
        return ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            model=settings.OPENAI_MODEL_NAME,
            temperature=kwargs.get("temperature", 0.3),
        )

    if provider != "mock":
        logger.warning(
            "LLM_PROVIDER=%s has no usable API key — using deterministic mock provider", provider
        )
    return MockChatModel(state=state, **kwargs)


def has_llm_credentials() -> bool:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "groq":
        return bool(settings.GROQ_API_KEY)
    if provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    return True  # mock needs nothing
