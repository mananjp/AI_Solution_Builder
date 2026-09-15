"""
AI Solution Builder — Pluggable LLM Provider Layer

Provides a single factory (`get_llm`) that resolves the configured
LLM_PROVIDER (groq | openai | mock) and returns a chat model with an
`ainvoke(messages)` method. When a provider API key is missing the
module falls back to the deterministic mock provider so development
and tests run without network access or credentials.

The mock provider inspects the system prompt to return valid,
node-specific JSON so the full LangGraph pipeline completes offline.

Supports multi-key rotation for Groq: when a key hits 429, the next
key in the pool is used automatically.
"""

import asyncio
import itertools
import json
import logging
import time
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 1
BASE_DELAY = 1  # seconds — responsive backoff for 429s
_COOLDOWN_SECONDS = 15  # how long a rate-limited key is skipped


class _GroqKeyPool:
    """Round-robin pool of Groq API keys with per-key cooldown on 429."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = [k for k in keys if k]
        self._cycle = itertools.cycle(range(len(self._keys)))
        self._cooldowns: dict[int, float] = {}  # index → epoch when key is usable again
        self._lock = asyncio.Lock()
        if not self._keys:
            logger.warning("GroqKeyPool initialised with zero usable keys")

    def _available_indices(self) -> list[int]:
        now = time.time()
        return [
            i for i in range(len(self._keys))
            if self._cooldowns.get(i, 0) <= now
        ]

    async def next_key(self) -> str | None:
        """Return the next available key, or None if all are cooled down."""
        async with self._lock:
            available = self._available_indices()
            if not available:
                return None
            # Pick the next key in round-robin from the available set
            idx = next(self._cycle)
            while idx not in available:
                idx = next(self._cycle)
            return self._keys[idx]

    async def mark_rate_limited(self, key: str) -> None:
        """Put a key on cooldown for _COOLDOWN_SECONDS."""
        async with self._lock:
            try:
                idx = self._keys.index(key)
                self._cooldowns[idx] = time.time() + _COOLDOWN_SECONDS
                logger.warning(
                    "Groq key [...%s] rate-limited — cooling down for %ds (pool size=%d)",
                    key[-6:],
                    _COOLDOWN_SECONDS,
                    len(self._keys),
                )
            except ValueError:
                pass

    @property
    def key_count(self) -> int:
        return len(self._keys)


def _build_groq_key_pool() -> _GroqKeyPool:
    """Collect all configured Groq API keys into a pool."""
    keys = [
        settings.GROQ_API_KEY,
        settings.GROQ_API_KEY_2,
        settings.GROQ_API_KEY_3,
    ]
    return _GroqKeyPool(keys)


# Module-level singleton (created once at import)
_groq_pool: _GroqKeyPool | None = None


def _get_groq_pool() -> _GroqKeyPool:
    global _groq_pool
    if _groq_pool is None:
        _groq_pool = _build_groq_key_pool()
        logger.info("Groq key pool: %d key(s) loaded", _groq_pool.key_count)
    return _groq_pool


async def invoke_with_retry(
    llm: Any,
    messages: list,
    *,
    max_retries: int = MAX_RETRIES,
) -> Any:
    """Call ``llm.ainvoke`` with exponential back-off on rate-limit (429) errors.

    For Groq, the ``llm`` is typically a ``_GroqKeyRotator`` that handles
    key rotation internally on 429. This function adds an outer retry loop
    for any remaining transient failures.

    Non-429 errors are raised immediately.  Returns the LLM response on
    success or the last exception after exhausting retries.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            last_exc = exc
            err_text = str(exc).lower()
            is_retryable = (
                "429" in err_text
                or "413" in err_text
                or "rate" in err_text
                or "too many requests" in err_text
                or "payload too large" in err_text
                or "tokens per minute" in err_text
            )
            if not is_retryable or attempt == max_retries:
                raise
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(
                "Rate-limited (attempt %d/%d) — retrying in %ds: %s",
                attempt + 1,
                max_retries + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]

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
        try:
            content = _build_mock_content(messages, self.state)
        except Exception as e:
            logger.warning("MockLLM build failed: %s — returning fallback", e)
            content = json.dumps({
                "error": "Mock generation failed",
                "status": "fallback",
                "message": str(e),
            })
        logger.debug("MockLLM returned %d characters", len(content))
        return MockMessage(content)


class _GroqKeyRotator:
    """Wraps the key pool — creates a fresh ChatGroq on each call, rotating
    keys when a 429 is detected. The node calls
    ``invoke_with_retry(rotator, messages)`` and the rotator transparently
    picks a new key for each attempt."""

    def __init__(self, pool: _GroqKeyPool, **default_kwargs: Any) -> None:
        self._pool = pool
        self._default_kwargs = default_kwargs
        self._current_key: str | None = None
        self._llm: ChatGroq | None = None

    async def _ensure_llm(self) -> ChatGroq:
        key = await self._pool.next_key()
        if key is None:
            raise RuntimeError("All Groq API keys are rate-limited — try again later")
        if key != self._current_key:
            self._current_key = key
            self._llm = ChatGroq(
                api_key=SecretStr(key),
                max_retries=0,  # disable SDK-level retries; we handle retry + rotation ourselves
                **self._default_kwargs,
            )
            logger.debug("Groq: switched to key [...%s]", key[-6:])
        return self._llm

    async def ainvoke(self, messages: list[Any]) -> Any:
        llm = await self._ensure_llm()
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            err_text = str(exc).lower()
            is_retryable = (
                "429" in err_text
                or "413" in err_text
                or "rate" in err_text
                or "too many requests" in err_text
                or "payload too large" in err_text
                or "tokens per minute" in err_text
            )
            if is_retryable and self._current_key:
                await self._pool.mark_rate_limited(self._current_key)
                # Rotate to next key and retry once
                llm = await self._ensure_llm()
                return await llm.ainvoke(messages)
            raise


def get_llm(**kwargs: Any) -> Any:
    """Resolve the configured LLM provider.

    Accepts temperature/max_tokens overrides. Falls back to the mock provider
    when the configured provider has no API key (dev/test convenience).

    For Groq, returns a ``_GroqKeyRotator`` that automatically rotates
    through all configured API keys on 429 rate-limit errors.
    """
    provider = settings.LLM_PROVIDER.lower()

    # The mock provider uses `state` to build process/code payloads; strip it
    # from the kwargs forwarded to real providers.
    state = kwargs.pop("state", {})

    if provider == "groq" and settings.GROQ_API_KEY:
        pool = _get_groq_pool()
        return _GroqKeyRotator(
            pool,
            model=settings.GROQ_MODEL_NAME,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2048),
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
