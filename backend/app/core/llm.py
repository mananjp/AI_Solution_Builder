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

from langchain_core.messages import SystemMessage
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


def _build_mock_content(messages: list[Any], state: dict[str, Any]) -> str:
    """Return node-appropriate JSON based on the system prompt marker."""
    system_text = ""
    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_text = str(msg.content)

    if "Business Analyst Agent" in system_text:
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
