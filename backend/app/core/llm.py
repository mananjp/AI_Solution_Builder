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

import json
import logging
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


def _mock_ai_developer(messages: list[Any]) -> dict[str, Any]:
    user_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_text = str(getattr(msg, "content", ""))

    lower = user_text.lower()
    if any(
        k in lower
        for k in (
            "agent",
            "bot",
            "assistant",
            "copilot",
            "llm",
            "ai",
            "autonomous",
            "orchestrator",
            "rag",
            "prompt",
        )
    ):
        app_type = "Autonomous AI Agent System"
        entities = ["Agents", "Tools", "Conversations", "Messages", "Executions"]
        endpoints = [
            "/api/v1/agents",
            "/api/v1/agents/{agent_id}/run",
            "/api/v1/tools",
            "/api/v1/conversations",
            "/api/v1/executions",
        ]
    elif any(
        k in lower
        for k in ("retail", "store", "ecommerce", "inventory", "pos", "shop", "product", "stock")
    ):
        app_type = "Omnichannel Retail & Inventory Platform"
        entities = ["Products", "Orders", "Customers", "Inventory"]
        endpoints = ["/api/v1/products", "/api/v1/orders", "/api/v1/inventory"]
    elif any(
        k in lower
        for k in ("health", "clinic", "doctor", "patient", "medical", "telehealth", "ehr")
    ):
        app_type = "Healthcare & Clinic Management System"
        entities = ["Patients", "Doctors", "Appointments", "Prescriptions"]
        endpoints = ["/api/v1/patients", "/api/v1/appointments", "/api/v1/records"]
    elif any(
        k in lower
        for k in ("logistics", "fleet", "dispatch", "driver", "freight", "truck", "shipment")
    ):
        app_type = "Logistics & Fleet Dispatch Platform"
        entities = ["Shipments", "Vehicles", "Drivers", "Routes"]
        endpoints = ["/api/v1/shipments", "/api/v1/routes", "/api/v1/drivers"]
    elif any(k in lower for k in ("crm", "lead", "client", "sales", "deal")):
        app_type = "CRM & Sales Pipeline Platform"
        entities = ["Leads", "Clients", "Deals", "Activities"]
        endpoints = ["/api/v1/leads", "/api/v1/clients", "/api/v1/deals"]
    elif any(k in lower for k in ("todo", "task", "project", "kanban", "sprint")):
        app_type = "Project & Task Management System"
        entities = ["Projects", "Tasks", "Milestones", "Tags"]
        endpoints = ["/api/v1/projects", "/api/v1/tasks"]
    elif any(k in lower for k in ("finance", "invoice", "billing", "payment", "expense")):
        app_type = "Finance & Invoicing Platform"
        entities = ["Invoices", "Transactions", "Expenses", "Accounts"]
        endpoints = ["/api/v1/invoices", "/api/v1/transactions", "/api/v1/expenses"]
    elif any(k in lower for k in ("property", "real estate", "listing", "tenant", "rental")):
        app_type = "Real Estate & Property Management"
        entities = ["Properties", "Units", "Leases", "Tenants"]
        endpoints = ["/api/v1/properties", "/api/v1/units", "/api/v1/leases"]
    elif any(k in lower for k in ("course", "student", "teacher", "learning", "lms")):
        app_type = "Education & Learning Management System"
        entities = ["Courses", "Lessons", "Students", "Enrollments"]
        endpoints = ["/api/v1/courses", "/api/v1/lessons", "/api/v1/students"]
    else:
        app_type = "Full-Stack Web Application"
        entities = ["Users", "Items", "Categories", "Activities"]
        endpoints = ["/api/v1/items", "/api/v1/categories", "/api/v1/users"]

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


_MOCK_SPEC_MARKER = "You design SMALL but REAL working apps"  # app_spec.SPEC_SYSTEM


def _mock_app_spec(messages: list[Any]) -> dict[str, Any]:
    """Deterministic valid AppSpec JSON for offline/mock mode (no keyword templates).

    Picks entities from the user text only to give the spec relevance; it never
    substitutes canned domain templates the way the legacy heuristic did.
    """
    user_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_text += "\n" + str(getattr(msg, "content", ""))

    lower = user_text.lower()
    if any(
        k in lower
        for k in (
            "agent",
            "bot",
            "assistant",
            "copilot",
            "llm",
            "autonomous",
            "orchestrator",
            "rag",
            "prompt",
        )
    ):
        entities = [("agent", "agents"), ("tool", "tools"), ("conversation", "conversations")]
    elif any(k in lower for k in ("project", "task", "kanban", "sprint", "todo")):
        entities = [("project", "projects"), ("task", "tasks")]
    elif any(k in lower for k in ("retail", "store", "inventory", "product", "stock", "pos")):
        entities = [("product", "products"), ("order", "orders")]
    elif any(k in lower for k in ("invoice", "expense", "billing", "payment", "accounting")):
        entities = [("invoice", "invoices"), ("expense", "expenses")]
    else:
        entities = [("item", "items"), ("category", "categories")]

    spec_entities = [
        {
            "name": name,
            "plural": plural,
            "description": f"{name} managed by the app",
            "fields": [
                {"name": "name", "type": "string", "required": True, "description": "Display name"},
                {"name": "description", "type": "text", "required": False, "description": "Notes"},
            ],
        }
        for name, plural in entities
    ]

    screens = [
        {
            "name": "dashboard",
            "route": "/",
            "purpose": "Overview of managed records",
            "uses_entities": [name for name, _ in entities],
            "uses_actions": [],
            "key_interactions": ["view records"],
        },
        *[
            {
                "name": f"{name}_management",
                "route": f"/{plural}",
                "purpose": f"Manage {plural}",
                "uses_entities": [name],
                "uses_actions": [],
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
        "app_name": "My App",
        "one_liner": "A small working application",
        "core_value": "",
        "assumptions": [],
        "entities": spec_entities,
        "actions": [],
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
                "suggested_answers": ["DPDP Act (India)", "GDPR (Europe)", "Standard commercial privacy"],
            },
            {
                "id": "q-scale-1",
                "question": "What is the expected concurrent user load and availability SLA?",
                "category": "scale",
                "why_it_matters": "Drives auto-scaling, caching, and backup/recovery design decisions.",
                "suggested_answers": ["Internal team (<50 users)", "100-1,000 users", "10,000+ users"],
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
