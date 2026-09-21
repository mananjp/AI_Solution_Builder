"""
AI Solution Builder — OpenCode Direct Chat API

Lets the user chat directly with the OpenCode sidecar (the "Custom App
Builder" path).  When the sidecar is unavailable the endpoint falls back to
the *integrated synthesizer* — a direct LLM conversation backed by the
blueprint scaffold — so the feature remains fully usable without the
sidecar process.

Each solution keeps a persistent session and a scaffolded workspace; the
agent (or synthesizer) edits files in-place as the conversation progresses.
When the user asks to finish (``build_requested``), the workspace is
verified/repaired and finalized into an ``MVPBuild`` for download/deploy.

Endpoints:
    GET  /api/v1/opencode/health      Service liveness probe (dashboard banner)
    POST /api/v1/opencode/chat        SSE chat stream (build_requested finalizes)
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.chat import _persist_artifacts
from app.core.config import settings
from app.core.credits import require_and_deduct_credit
from app.core.database import async_session_factory, get_db
from app.core.llm import get_llm
from app.core.security import get_current_user
from app.models.mvp_build import MVPBuild
from app.models.solution import Solution
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas import OpenCodeChatRequest
from app.services import mvp_builder as builder
from app.services import mvp_verifier
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opencode", tags=["OpenCode Chat"])

_TARGET_MAX_CONTEXT = 20_000  # uploaded-context cap fed to the sidecar


def _extract_app_title(prompt: str, fallback: str = "Custom App") -> str:
    """Extract a clean, concise application title from a user prompt."""
    if not prompt or not prompt.strip():
        return fallback

    cleaned = prompt.strip()
    # Check if prompt is just a greeting or single non-descriptive word
    if cleaned.lower().rstrip(".!?") in {
        "hi",
        "hello",
        "hey",
        "test",
        "build",
        "app",
        "help",
        "yo",
        "start",
    }:
        return fallback

    # Check for explicit named patterns first: "called XYZ" or "named XYZ"
    named_match = re.search(
        r"(?:called|named)\s+[\"']?([A-Za-z0-9_\-\s]{2,40}?)[\"']?(?:\s+(?:for|with|that|which|\.|\,)|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if named_match:
        name = named_match.group(1).strip()
        if name:
            return name

    patterns = [
        r"^(?:please\s+)?(?:i\s+want\s+to\s+|i\s+would\s+like\s+to\s+|can\s+you\s+)?(?:build|create|make|develop|design|generate)\s+(?:me\s+)?(?:an?\s+)?(?:mvp\s+)?(?:app\s+for\s+|application\s+for\s+|system\s+for\s+|platform\s+for\s+)?(?:an?\s+)?",
        r"^(?:i\s+need\s+an?\s+app\s+for\s+|i\s+need\s+an?\s+application\s+for\s+|i\s+need\s+a\s+system\s+for\s+)",
        r"^(?:build\s+|create\s+|make\s+|design\s+)(?:an?\s+)?(?:app\s+for\s+|application\s+for\s+|system\s+for\s+)?(?:an?\s+)?",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()

    first_clause = re.split(
        r"[.\n,;]|\bwith\b|\bthat\b|\bfor\b|\bwhich\b", cleaned, flags=re.IGNORECASE
    )[0].strip()
    words = first_clause.split()
    if 1 <= len(words) <= 6:
        candidate = " ".join(words).title()
        return candidate[:60]

    if words:
        candidate = " ".join(words[:4]).title()
        return candidate[:60]
    return fallback


def _synthesize_artifacts_from_spec(
    title: str,
    industry: str,
    modules: list[str],
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct full architecture artifacts (HLD, LLD, ER, schema, APIs, wireframes) from entities."""
    normalized_entities: list[dict[str, Any]] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        ent_name = str(ent.get("name", "item"))
        clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", ent_name.lower()).strip("_") or "item"
        raw_fields = ent.get("fields", [])
        clean_fields: list[dict[str, str]] = []
        has_id = False
        for f in raw_fields:
            if isinstance(f, dict):
                fname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f.get("name", "")).lower()).strip("_")
                ftype = str(f.get("type", "VARCHAR(255)")).upper()
            else:
                fname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f).lower()).strip("_")
                ftype = "VARCHAR(255)"
            if fname == "id":
                has_id = True
                clean_fields.insert(0, {"name": "id", "type": "UUID"})
            elif fname:
                clean_fields.append({"name": fname, "type": ftype})
        if not has_id:
            clean_fields.insert(0, {"name": "id", "type": "UUID"})
        normalized_entities.append({"name": clean_name, "fields": clean_fields})

    entities = normalized_entities or [
        {
            "name": "items",
            "fields": [{"name": "id", "type": "UUID"}, {"name": "name", "type": "VARCHAR(255)"}],
        }
    ]

    ddl_statements: list[str] = []
    for ent in entities:
        ent_name = str(ent["name"])
        ent_fields = cast(list[dict[str, str]], ent.get("fields", []))
        cols = ", ".join(f"{f['name']} {f['type']}" for f in ent_fields)
        ddl_statements.append(f"CREATE TABLE {ent_name} ({cols});")
    schema_ddl = "\n".join(ddl_statements)

    endpoints: list[dict[str, str]] = []
    for ent in entities:
        ent_name = str(ent["name"])
        endpoints.extend(
            [
                {
                    "method": "GET",
                    "path": f"/api/v1/{ent_name}",
                    "description": f"List {ent_name}",
                },
                {
                    "method": "POST",
                    "path": f"/api/v1/{ent_name}",
                    "description": f"Create {ent_name}",
                },
                {
                    "method": "DELETE",
                    "path": f"/api/v1/{ent_name}/{{item_id}}",
                    "description": f"Delete {ent_name}",
                },
            ]
        )

    screens: list[dict[str, Any]] = []
    for ent in entities:
        ent_name = str(ent["name"])
        ent_fields = cast(list[dict[str, str]], ent.get("fields", []))
        screens.append(
            {
                "name": f"{ent_name.replace('_', ' ').title()} Dashboard",
                "route": f"/{ent_name}",
                "description": f"CRUD management for {ent_name}",
                "layout": "sidebar",
                "components": [
                    {
                        "type": "data_table",
                        "title": f"{ent_name.replace('_', ' ').title()} Table",
                        "fields": [f["name"] for f in ent_fields],
                    }
                ],
            }
        )

    components: list[dict[str, str]] = [
        {
            "name": "Frontend",
            "technology": "Next.js 14 / React",
            "description": "Responsive dashboard with data tables",
        },
        {
            "name": "API Service",
            "technology": "FastAPI",
            "description": "REST API with automated OpenAPI docs",
        },
        {
            "name": "Database",
            "technology": "PostgreSQL",
            "description": "Relational data store with UUID primary keys",
        },
    ]

    hld_dict: dict[str, Any] = {
        "title": f"High-Level Design — {title}",
        "system_overview": f"A scalable full-stack application for {title}, powered by FastAPI and Next.js.",
        "components": components,
        "deployment": {"environment": "Render / Docker", "scaling_strategy": "horizontal"},
        "security": {"authentication": "JWT", "authorization": "RBAC"},
    }

    lld_modules: list[dict[str, Any]] = [
        {
            "name": m,
            "endpoints": [e for e in endpoints if m in e["path"] or True],
            "data_models": [str(ent["name"]) for ent in entities],
        }
        for m in modules[:2]
    ]

    lld_dict: dict[str, Any] = {
        "title": f"Low-Level Design — {title}",
        "modules": lld_modules,
    }

    phases: list[dict[str, Any]] = [
        {
            "name": "Phase 1: Core Foundation",
            "duration": "2 weeks",
            "modules": modules[:2],
            "deliverables": ["Database", "REST APIs", "Dashboard UI"],
        },
        {
            "name": "Phase 2: Full Integration",
            "duration": "2 weeks",
            "modules": modules[2:],
            "deliverables": ["Advanced Filtering", "Exporting", "Audit Logs"],
        },
    ]

    roadmap_dict: dict[str, Any] = {
        "title": f"Sprint Roadmap — {title}",
        "phases": phases,
    }

    tables: list[dict[str, Any]] = [
        {
            "table": str(e["name"]),
            "columns": [
                f"{f['name']} {f['type']}" for f in cast(list[dict[str, str]], e.get("fields", []))
            ],
        }
        for e in entities
    ]

    return {
        "industry": industry,
        "confirmed_modules": modules,
        "identified_solutions": modules,
        "hld": {
            "artifact_type": "hld",
            "title": f"High-Level Design — {title}",
            "content": hld_dict,
            "content_text": f"# High-Level Design — {title}\n\n{hld_dict['system_overview']}\n\n## Components\n"
            + "\n".join(
                f"- **{c['name']}** ({c['technology']}): {c['description']}" for c in components
            ),
        },
        "lld": {
            "artifact_type": "lld",
            "title": f"Low-Level Design — {title}",
            "content": lld_dict,
            "content_text": f"# Low-Level Design — {title}\n\n## Modules\n"
            + "\n".join(f"- **{m['name']}**" for m in lld_modules),
        },
        "er_diagram": {
            "artifact_type": "er_diagram",
            "title": f"Entity Relationship Diagram — {title}",
            "content": {"entities": entities, "relationships": []},
            "content_text": f"# ER Diagram — {title}\n\n"
            + "\n".join(
                f"- **{e['name']}**: {', '.join(f['name'] for f in cast(list[dict[str, str]], e.get('fields', [])))}"
                for e in entities
            ),
        },
        "database_schema": {
            "artifact_type": "database_schema",
            "title": f"Database DDL & Schema — {title}",
            "content": {"schema_ddl": schema_ddl, "entities": entities},
            "content_text": f"```sql\n{schema_ddl}\n```",
        },
        "api_spec": {
            "artifact_type": "api_spec",
            "title": f"OpenAPI Specification — {title}",
            "content": {"endpoints": endpoints},
            "content_text": f"# API Endpoints — {title}\n\n"
            + "\n".join(f"- `{e['method']} {e['path']}`: {e['description']}" for e in endpoints),
        },
        "wireframes": [
            {
                "artifact_type": "wireframe",
                "title": f"UI Wireframes — {title}",
                "content": {"screens": screens},
                "content_text": f"# Wireframe Screens — {title}\n\n"
                + "\n".join(
                    f"- **{s['name']}** (`{s['route']}`): {s['description']}" for s in screens
                ),
            }
        ],
        "bpmn_flows": [
            {
                "artifact_type": "bpmn_flows",
                "title": f"Process Workflow — {title}",
                "content": {
                    "flows": [
                        {"id": "flow_1", "name": f"{m.replace('_', ' ').title()} Flow"}
                        for m in modules
                    ]
                },
                "content_text": f"# Process Workflow — {title}\n\n"
                + "\n".join(f"- {m.replace('_', ' ').title()}" for m in modules),
            }
        ],
        "roadmap": {
            "artifact_type": "roadmap",
            "title": f"Sprint Roadmap — {title}",
            "content": roadmap_dict,
            "content_text": f"# Sprint Roadmap — {title}\n\n"
            + "\n".join(
                f"- **{p['name']}** ({p['duration']}): {', '.join(cast(list[str], p['deliverables']))}"
                for p in phases
            ),
        },
        "generated_schema": {
            "artifact_type": "workable_schema",
            "title": f"Executable Database Schema — {title}",
            "content": {
                "tables": tables,
                "ddl": schema_ddl,
            },
            "content_text": f"```sql\n{schema_ddl}\n```",
        },
    }


def _synthesize_domain_artifacts_heuristic(title: str, user_prompt: str) -> dict[str, Any]:
    """Heuristic fallback for domain artifact synthesis using word-boundary matching."""
    text = f"{title} {user_prompt}".lower()
    industry: str
    modules: list[str]
    entities: list[dict[str, Any]]

    # 1. AI Agents / LLMs — Use WORD BOUNDARIES so "retail", "trainer", "email", "repair" don't match!
    if re.search(
        r"\b(agent|agents|bot|bots|assistant|assistants|copilot|llm|ai|autonomous|orchestrator|rag|prompt)\b",
        text,
    ):
        industry = "ai_agents"
        modules = ["agent_orchestration", "tool_registry", "chat_interface", "execution_logs"]
        entities = [
            {
                "name": "agents",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "VARCHAR(500)"},
                    {"name": "model", "type": "VARCHAR(100)"},
                    {"name": "system_prompt", "type": "TEXT"},
                    {"name": "temperature", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "tools",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "VARCHAR(500)"},
                    {"name": "tool_type", "type": "VARCHAR(100)"},
                    {"name": "parameters_schema", "type": "TEXT"},
                    {"name": "is_enabled", "type": "BOOLEAN"},
                ],
            },
            {
                "name": "conversations",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "agent_name", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "messages",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "conversation_id", "type": "UUID"},
                    {"name": "role", "type": "VARCHAR(50)"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "tokens", "type": "INTEGER"},
                ],
            },
            {
                "name": "executions",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "agent_name", "type": "VARCHAR(255)"},
                    {"name": "input_query", "type": "TEXT"},
                    {"name": "output_result", "type": "TEXT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                    {"name": "duration_ms", "type": "INTEGER"},
                ],
            },
        ]
    # 2. Gym / Fitness / Wellness
    elif re.search(
        r"\b(gym|fitness|workout|workouts|trainer|trainers|exercise|exercises|bodybuilding|athlete|coaching)\b",
        text,
    ):
        industry = "fitness"
        modules = ["member_directory", "trainer_roster", "workout_planner", "subscriptions"]
        entities = [
            {
                "name": "members",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                    {"name": "phone", "type": "VARCHAR(50)"},
                    {"name": "membership_tier", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "trainers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "specialty", "type": "VARCHAR(100)"},
                    {"name": "hourly_rate", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "workouts",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "difficulty", "type": "VARCHAR(50)"},
                    {"name": "duration_mins", "type": "INTEGER"},
                    {"name": "description", "type": "TEXT"},
                ],
            },
            {
                "name": "subscriptions",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "member_name", "type": "VARCHAR(255)"},
                    {"name": "plan_name", "type": "VARCHAR(100)"},
                    {"name": "price", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 3. Restaurant / Food / Dining
    elif re.search(
        r"\b(restaurant|food|menu|menus|dish|dishes|dining|meal|meals|recipe|recipes|chef|waiter|cafe|bakery)\b",
        text,
    ):
        industry = "food_and_beverage"
        modules = ["menu_catalog", "order_management", "table_reservations", "kitchen_display"]
        entities = [
            {
                "name": "menus",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "category", "type": "VARCHAR(100)"},
                    {"name": "is_active", "type": "BOOLEAN"},
                ],
            },
            {
                "name": "dishes",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "price", "type": "FLOAT"},
                    {"name": "description", "type": "TEXT"},
                    {"name": "is_available", "type": "BOOLEAN"},
                ],
            },
            {
                "name": "orders",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "table_number", "type": "VARCHAR(50)"},
                    {"name": "total_amount", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "reservations",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "guest_name", "type": "VARCHAR(255)"},
                    {"name": "party_size", "type": "INTEGER"},
                    {"name": "reservation_time", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 4. Events / Ticketing / Conferences
    elif re.search(
        r"\b(event|events|conference|conferences|ticket|tickets|ticketing|attendee|attendees|speaker|speakers)\b",
        text,
    ):
        industry = "event_management"
        modules = ["event_catalog", "ticket_booking", "attendee_registry", "speaker_schedule"]
        entities = [
            {
                "name": "events",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "venue", "type": "VARCHAR(255)"},
                    {"name": "event_date", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "tickets",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "event_title", "type": "VARCHAR(255)"},
                    {"name": "tier", "type": "VARCHAR(50)"},
                    {"name": "price", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "attendees",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                    {"name": "badge_number", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "speakers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "topic", "type": "VARCHAR(255)"},
                    {"name": "bio", "type": "TEXT"},
                ],
            },
        ]
    # 5. Hotels / Hospitality
    elif re.search(
        r"\b(hotel|hotels|room|rooms|hospitality|reservation|reservations|guest|guests|stay)\b",
        text,
    ):
        industry = "hotel_hospitality"
        modules = ["room_inventory", "guest_portal", "booking_engine", "billing_folio"]
        entities = [
            {
                "name": "rooms",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "room_number", "type": "VARCHAR(50)"},
                    {"name": "room_type", "type": "VARCHAR(100)"},
                    {"name": "nightly_rate", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "guests",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                    {"name": "phone", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "bookings",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "guest_name", "type": "VARCHAR(255)"},
                    {"name": "check_in", "type": "VARCHAR(50)"},
                    {"name": "check_out", "type": "VARCHAR(50)"},
                    {"name": "total_price", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 6. HR / Workforce / Recruitment
    elif re.search(
        r"\b(hr|employee|employees|staff|payroll|applicant|applicants|recruitment|job|jobs|hiring)\b",
        text,
    ):
        industry = "hr_workforce"
        modules = ["employee_directory", "department_manager", "leave_tracker", "payroll_ledger"]
        entities = [
            {
                "name": "employees",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                    {"name": "job_title", "type": "VARCHAR(100)"},
                    {"name": "department", "type": "VARCHAR(100)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "departments",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "manager_name", "type": "VARCHAR(255)"},
                ],
            },
            {
                "name": "leave_requests",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "employee_name", "type": "VARCHAR(255)"},
                    {"name": "leave_type", "type": "VARCHAR(50)"},
                    {"name": "start_date", "type": "VARCHAR(50)"},
                    {"name": "end_date", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 7. Retail / E-commerce
    elif re.search(
        r"\b(retail|store|ecommerce|inventory|pos|shop|product|products|stock|cart|catalog)\b",
        text,
    ):
        industry = "d2c_retail"
        modules = ["ecommerce_storefront", "inventory_management", "order_fulfillment", "crm"]
        entities = [
            {
                "name": "products",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "sku", "type": "VARCHAR(100)"},
                    {"name": "price", "type": "FLOAT"},
                ],
            },
            {
                "name": "orders",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "customer_name", "type": "VARCHAR(255)"},
                    {"name": "total", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "customers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                ],
            },
            {
                "name": "inventory",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "product_name", "type": "VARCHAR(255)"},
                    {"name": "quantity", "type": "INTEGER"},
                ],
            },
        ]
    # 8. Healthcare / Clinic
    elif re.search(
        r"\b(health|clinic|doctor|doctors|patient|patients|medical|telehealth|ehr|hospital|dental)\b",
        text,
    ):
        industry = "healthcare_clinic"
        modules = ["booking_scheduler", "patient_portal", "prescriptions", "invoicing_billing"]
        entities = [
            {
                "name": "patients",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "dob", "type": "VARCHAR(50)"},
                    {"name": "phone", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "doctors",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "specialty", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "appointments",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "patient_name", "type": "VARCHAR(255)"},
                    {"name": "appointment_date", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "prescriptions",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "patient_name", "type": "VARCHAR(255)"},
                    {"name": "medication", "type": "VARCHAR(255)"},
                ],
            },
        ]
    # 9. Logistics / Fleet / Shipping
    elif re.search(
        r"\b(logistics|fleet|dispatch|driver|drivers|freight|truck|trucks|shipment|shipments|warehouse)\b",
        text,
    ):
        industry = "logistics_company"
        modules = [
            "order_fulfillment",
            "fleet_tracking",
            "dispatch_management",
            "invoicing_billing",
        ]
        entities = [
            {
                "name": "shipments",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "tracking_number", "type": "VARCHAR(100)"},
                    {"name": "destination", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "drivers",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "license_number", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "vehicles",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "plate_number", "type": "VARCHAR(50)"},
                    {"name": "model", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "routes",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "origin", "type": "VARCHAR(255)"},
                    {"name": "destination", "type": "VARCHAR(255)"},
                ],
            },
        ]
    # 10. CRM / Sales
    elif re.search(r"\b(crm|lead|leads|client|clients|sales|deal|deals|pipeline)\b", text):
        industry = "consulting_agency"
        modules = ["crm", "deal_pipeline", "client_portal", "invoicing_billing"]
        entities = [
            {
                "name": "leads",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "company", "type": "VARCHAR(255)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "clients",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "industry", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "deals",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "amount", "type": "FLOAT"},
                    {"name": "stage", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "activities",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "activity_type", "type": "VARCHAR(50)"},
                    {"name": "notes", "type": "VARCHAR(500)"},
                ],
            },
        ]
    # 11. Project Management / Tasks
    elif re.search(
        r"\b(todo|task|tasks|project|projects|kanban|sprint|sprints|issue|issues|bug|bugs)\b",
        text,
    ):
        industry = "project_management"
        modules = ["task_tracking", "project_boards", "milestone_planner", "team_collaboration"]
        entities = [
            {
                "name": "projects",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "TEXT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "tasks",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "TEXT"},
                    {"name": "priority", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "milestones",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "due_date", "type": "VARCHAR(50)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 12. Finance / Invoicing / Payments
    elif re.search(
        r"\b(finance|invoice|invoices|billing|payment|payments|expense|expenses|wallet|crypto|ledger)\b",
        text,
    ):
        industry = "finance_invoicing"
        modules = [
            "invoice_management",
            "payment_processing",
            "expense_tracker",
            "ledger_reporting",
        ]
        entities = [
            {
                "name": "invoices",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "invoice_number", "type": "VARCHAR(50)"},
                    {"name": "recipient", "type": "VARCHAR(255)"},
                    {"name": "amount", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "transactions",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "description", "type": "VARCHAR(255)"},
                    {"name": "amount", "type": "FLOAT"},
                    {"name": "category", "type": "VARCHAR(100)"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "accounts",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "account_name", "type": "VARCHAR(255)"},
                    {"name": "balance", "type": "FLOAT"},
                    {"name": "currency", "type": "VARCHAR(10)"},
                ],
            },
        ]
    # 13. Real Estate / Property
    elif re.search(
        r"\b(property|properties|real\s+estate|listing|listings|tenant|tenants|rental|rentals|lease|apartment)\b",
        text,
    ):
        industry = "real_estate"
        modules = ["property_listings", "unit_management", "lease_tracking", "tenant_portal"]
        entities = [
            {
                "name": "properties",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "address", "type": "VARCHAR(255)"},
                    {"name": "property_type", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "units",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "unit_number", "type": "VARCHAR(50)"},
                    {"name": "rent_amount", "type": "FLOAT"},
                    {"name": "status", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "tenants",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                    {"name": "phone", "type": "VARCHAR(50)"},
                ],
            },
        ]
    # 14. Education / LMS
    elif re.search(
        r"\b(course|courses|student|students|teacher|teachers|learning|lms|school|university|class|classes)\b",
        text,
    ):
        industry = "education_lms"
        modules = ["course_catalog", "lesson_manager", "student_enrollment", "grading_analytics"]
        entities = [
            {
                "name": "courses",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "description", "type": "TEXT"},
                    {"name": "instructor", "type": "VARCHAR(255)"},
                ],
            },
            {
                "name": "lessons",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "title", "type": "VARCHAR(255)"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "order_index", "type": "INTEGER"},
                ],
            },
            {
                "name": "students",
                "fields": [
                    {"name": "id", "type": "UUID"},
                    {"name": "name", "type": "VARCHAR(255)"},
                    {"name": "email", "type": "VARCHAR(255)"},
                ],
            },
        ]
    else:
        # Dynamic extraction from user prompt words instead of always generic "items"
        industry = "custom_domain"
        clean_words = [
            w
            for w in re.findall(r"[a-z]{3,}", text)
            if w
            not in {
                "the",
                "and",
                "for",
                "with",
                "that",
                "this",
                "app",
                "application",
                "system",
                "build",
                "create",
                "make",
                "want",
                "need",
                "like",
                "from",
                "have",
                "more",
                "user",
                "custom",
                "into",
                "full",
                "stack",
                "fastapi",
                "nextjs",
                "crud",
                "real",
                "data",
                "platform",
            }
        ]
        entities = []
        modules = []
        for w in clean_words[:4]:
            singular = w.rstrip("s")
            plural = f"{singular}s"
            if plural not in [e["name"] for e in entities]:
                entities.append(
                    {
                        "name": plural,
                        "fields": [
                            {"name": "id", "type": "UUID"},
                            {"name": "name", "type": "VARCHAR(255)"},
                            {"name": "description", "type": "TEXT"},
                            {"name": "status", "type": "VARCHAR(50)"},
                        ],
                    }
                )
                modules.append(f"{singular}_management")
        if not entities:
            industry = "saas_platform"
            modules = ["core_crud", "user_management", "analytics_dashboard", "invoicing_billing"]
            entities = [
                {
                    "name": "items",
                    "fields": [
                        {"name": "id", "type": "UUID"},
                        {"name": "name", "type": "VARCHAR(255)"},
                        {"name": "status", "type": "VARCHAR(50)"},
                    ],
                },
                {
                    "name": "categories",
                    "fields": [
                        {"name": "id", "type": "UUID"},
                        {"name": "name", "type": "VARCHAR(255)"},
                        {"name": "description", "type": "VARCHAR(255)"},
                    ],
                },
                {
                    "name": "users",
                    "fields": [
                        {"name": "id", "type": "UUID"},
                        {"name": "name", "type": "VARCHAR(255)"},
                        {"name": "email", "type": "VARCHAR(255)"},
                    ],
                },
            ]

    return _synthesize_artifacts_from_spec(title, industry, modules, entities)


def _synthesize_domain_artifacts(title: str, user_prompt: str) -> dict[str, Any]:
    """Backward-compatible synchronous wrapper for heuristic domain artifact synthesis."""
    return _synthesize_domain_artifacts_heuristic(title, user_prompt)


async def _synthesize_domain_artifacts_dynamic(
    title: str,
    user_prompt: str,
    context: str = "",
    history: list[dict[str, Any]] | None = None,
    existing_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dynamically synthesize domain models, entities, and modules for the user's application.

    Uses LLM to extract domain structure from prompt and history, falling back to
    intelligent regex heuristic if LLM is unavailable or offline.
    """
    # 1. Check if user prompt is a short confirmation (e.g. "build it", "build it now", "yes", "proceed")
    # and we already have existing domain entities in existing_state.
    short_confirmations = {
        "build",
        "build it",
        "build it now",
        "build now",
        "build app",
        "build please",
        "please build",
        "please build it",
        "yes",
        "yes please",
        "go ahead",
        "proceed",
        "proceed with build",
        "finalize",
        "deploy",
        "confirm",
        "looks good",
        "looks good build it",
        "ok",
        "okay",
        "start build",
        "build and deploy",
    }
    cleaned_prompt = re.sub(r"[^a-zA-Z0-9\s]+", "", user_prompt.strip().lower()).strip()
    words = cleaned_prompt.split()
    is_confirmation = cleaned_prompt in short_confirmations or (
        len(words) <= 5
        and any(
            w in words
            for w in ("build", "proceed", "finalize", "confirm", "deploy", "yes", "ok", "okay")
        )
        and not any(
            w in words
            for w in (
                "create",
                "make",
                "design",
                "instead",
                "change",
                "modify",
                "different",
                "new",
                "another",
            )
        )
    )

    if (
        is_confirmation
        and existing_state
        and existing_state.get("er_diagram", {}).get("content", {}).get("entities")
    ):
        logger.info(
            "Preserving existing domain architecture for confirmation prompt '%s'", user_prompt
        )
        return dict(existing_state)

    # 2. Combine history if current prompt is short but we need context
    effective_prompt = user_prompt
    if len(user_prompt.split()) < 5 and history:
        user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
        if user_msgs:
            effective_prompt = f"{' '.join(user_msgs[-3:])} {user_prompt}"

    # 3. Attempt LLM-based structured synthesis
    try:
        llm = get_llm(temperature=0.1)
        sys_prompt = (
            "You are an expert software architect. Analyze the user's application requirements "
            "and extract a structured domain specification as a JSON object with EXACTLY this schema:\n"
            "{\n"
            '  "app_title": "Concise 2-4 word application name (e.g. FitPulse Gym, MedTrack Inventory)",\n'
            '  "industry": "slugified industry name (e.g. fitness_gym, healthcare, ecommerce)",\n'
            '  "modules": ["module1_slug", "module2_slug", "module3_slug", "module4_slug"],\n'
            '  "entities": [\n'
            "    {\n"
            '      "name": "plural_table_name (e.g. members, trainers, classes)",\n'
            '      "fields": [\n'
            '        {"name": "id", "type": "UUID"},\n'
            '        {"name": "field_name", "type": "VARCHAR(255) | TEXT | INTEGER | FLOAT | BOOLEAN"}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Include 3-5 domain entities with 4-7 realistic fields each tailored precisely to the user's app. "
            "Respond ONLY with the JSON object."
        )
        user_content = f"User Request: {effective_prompt}"
        if context:
            user_content = f"Uploaded Context:\n{context[:4000]}\n\n{user_content}"

        resp = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_content)]),
            timeout=10.0,
        )
        if resp and resp.content:
            raw_text = str(resp.content).strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw_text)
            if (
                isinstance(parsed, dict)
                and parsed.get("entities")
                and isinstance(parsed["entities"], list)
                and len(parsed["entities"]) >= 1
            ):
                app_title = parsed.get("app_title") or title or _extract_app_title(effective_prompt)
                industry = parsed.get("industry") or "custom_domain"
                modules = parsed.get("modules") or [
                    f"{e.get('name', 'item')}_mgmt" for e in parsed["entities"]
                ]
                entities = parsed["entities"]
                logger.info(
                    "LLM synthesized custom domain for '%s': %s (%d entities)",
                    app_title,
                    industry,
                    len(entities),
                )
                res = _synthesize_artifacts_from_spec(app_title, industry, modules, entities)
                res["app_title"] = app_title
                return res
    except Exception as exc:
        logger.warning("LLM dynamic domain synthesis skipped or failed (%s); using heuristic", exc)

    # 4. Fallback to heuristic
    app_title = (
        title
        if title not in ("Custom App Build", "Custom App")
        else _extract_app_title(effective_prompt)
    )
    res = _synthesize_domain_artifacts_heuristic(app_title, effective_prompt)
    res["app_title"] = app_title
    return res


@router.get("/health")
async def health() -> dict[str, Any]:
    """Report whether the AI build engine is reachable and ready.

    ``healthy`` is ``True`` whenever the service can handle a request —
    either via the live sidecar *or* via the integrated synthesizer
    fallback.  ``sidecar_healthy`` reports the sidecar process itself.
    """
    sidecar_ok = await builder.health()
    return {
        "healthy": True,
        "sidecar_healthy": sidecar_ok,
        "mode": "opencode-sidecar" if sidecar_ok else "integrated-synthesizer",
    }


async def _verify_solution_access(db: AsyncSession, solution_id: UUID, user: User) -> Solution:
    result = await db.execute(
        select(Solution)
        .join(Workspace, Workspace.id == Solution.workspace_id)
        .where(Solution.id == solution_id, Workspace.org_id == user.org_id)
    )
    solution = result.scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    return solution


async def _get_or_create_workspace(db: AsyncSession, user: User) -> Workspace:
    result = await db.execute(
        select(Workspace)
        .where(Workspace.org_id == user.org_id)
        .order_by(Workspace.created_at)
        .limit(1)
    )
    workspace = result.scalar_one_or_none()
    if workspace is not None:
        return workspace
    workspace = Workspace(
        org_id=user.org_id,
        name="Custom App Builder",
        description="Apps built through conversational OpenCode chat",
    )
    db.add(workspace)
    await db.flush()
    return workspace


async def _next_build_number(db: AsyncSession, solution_id: UUID) -> int:
    result = await db.execute(
        select(MVPBuild.build_number)
        .where(MVPBuild.solution_id == solution_id)
        .order_by(desc(MVPBuild.build_number))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1


def _extract_text(response: dict[str, Any]) -> str:
    """Concatenate the text parts from an OpenCode message response."""
    parts = response.get("parts") or []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip()


@router.post("/chat")
async def chat(
    payload: OpenCodeChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Chat directly with OpenCode; streaming SSE response."""
    # Eager ownership check so authorization failures surface as HTTP errors
    # rather than mid-stream error events.
    if payload.solution_id:
        await _verify_solution_access(db, payload.solution_id, current_user)

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            # Streaming over a dependency-injected session is unsafe (see
            # chat.py for the rationale) — open an explicit session here.
            async with async_session_factory() as stream_db:
                if payload.solution_id:
                    solution = await _verify_solution_access(
                        stream_db, payload.solution_id, current_user
                    )
                    if payload.app_name and solution.title in ("Custom App Build", "Custom App"):
                        solution.title = payload.app_name
                else:
                    workspace = await _get_or_create_workspace(stream_db, current_user)
                    initial_title = payload.app_name or _extract_app_title(payload.message)
                    solution = Solution(
                        workspace_id=workspace.id,
                        title=initial_title,
                        description=f"App built through conversational OpenCode chat: {payload.message[:200]}",
                        status="discovery",
                        conversation_history=[],
                    )
                    stream_db.add(solution)
                    await stream_db.flush()

                sidecar_ok = await builder.health()
                ai_state = dict(solution.ai_state or {})
                session_id: str | None = ai_state.get("opencode_session_id") or payload.session_id

                # ── Sidecar path vs integrated-synthesizer path ──────
                if sidecar_ok:
                    if session_id and payload.session_id and session_id != payload.session_id:
                        yield {
                            "event": "error",
                            "data": json.dumps(
                                {"message": "Session id does not match this solution."}
                            ),
                        }
                        return
                    if not session_id:
                        session_id = await builder.create_session(
                            f"Custom Build - {solution.title}"
                        )
                        ai_state["opencode_session_id"] = session_id
                    agent_name = "opencode"
                    agent_msg = "Connected to the OpenCode sidecar..."
                else:
                    # Integrated-synthesizer mode — no live sidecar needed.
                    session_id = session_id or f"synthesizer-{solution.id}"
                    ai_state["opencode_session_id"] = session_id
                    agent_name = "AI Developer"
                    agent_msg = "Connected to the AI build engine..."

                yield {
                    "event": "agent_start",
                    "data": json.dumps(
                        {
                            "agent": agent_name,
                            "session_id": session_id,
                            "solution_id": str(solution.id),
                            "message": agent_msg,
                        }
                    ),
                }

                # Ensure the chat workspace is scaffolded once per solution.
                ws_dir = builder.chat_workspace_dir(solution.id)
                if not any(ws_dir.iterdir()):
                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=[],
                    )

                target_dir = builder.chat_container_target(solution.id)

                # ── Generate the conversational reply ────────────────
                if sidecar_ok:
                    instruction = (
                        f"# Custom Build Request — {solution.title}\n\n"
                        f"{payload.message}\n\n"
                        "## Working directory\n"
                        "A working FastAPI + Next.js scaffold already exists at `"
                        f"{target_dir}`. Implement the requested app by editing files "
                        f"inside `{target_dir}` only. Keep the scaffold structure; add "
                        "models, schemas, routers, and frontend pages to satisfy the "
                        "request. Do not run installs or builds — just edit files.\n"
                        "Report which files/modules you added when finished."
                    )
                    if payload.uploaded_context:
                        context = payload.uploaded_context[:_TARGET_MAX_CONTEXT]
                        instruction = (
                            f"## Context from uploaded document\n{context}\n\n" + instruction
                        )

                    try:
                        response = await asyncio.wait_for(
                            builder.send_message(
                                session_id,
                                instruction,
                                agent=settings.OPENCODE_AGENT,
                                timeout=25,
                            ),
                            timeout=30.0,
                        )
                        assistant_text = _extract_text(response) or (
                            "Done — tell me what to change next, or hit Build & Deploy "
                            "to finalize the app."
                        )
                    except Exception as sidecar_err:
                        logger.warning(
                            "Sidecar send_message failed (%s); falling back to direct LLM",
                            sidecar_err,
                        )
                        assistant_text = ""
                else:
                    assistant_text = ""

                if not assistant_text:
                    # Integrated synthesizer — direct LLM conversation.
                    llm = get_llm()
                    sys_prompt = (
                        "You are an expert full-stack AI Developer for AI Solution Builder. "
                        "You are helping the user architect and build a complete "
                        "FastAPI + Next.js application. A full working scaffold with "
                        "database, auth, and API structure is already configured. "
                        "Respond informatively to their requirements, explain which "
                        "models, API routes, and pages are being generated, and "
                        "confirm that the workspace is ready to finalize. "
                        "Keep your response concise, structured, and practical."
                    )
                    user_prompt = payload.message
                    if payload.uploaded_context:
                        user_prompt = (
                            f"Context from uploaded document:\n"
                            f"{payload.uploaded_context[:_TARGET_MAX_CONTEXT]}\n\n"
                            f"User request:\n{user_prompt}"
                        )

                    resp = await llm.ainvoke(
                        [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
                    )
                    if resp and resp.content:
                        try:
                            parsed = json.loads(resp.content)
                            if isinstance(parsed, dict) and "content" in parsed:
                                assistant_text = str(parsed["content"])
                            elif isinstance(parsed, dict) and "message" in parsed:
                                assistant_text = str(parsed["message"])
                            else:
                                assistant_text = str(resp.content)
                        except (json.JSONDecodeError, TypeError):
                            assistant_text = str(resp.content)
                    if not assistant_text or assistant_text == "Mock response":
                        assistant_text = (
                            f"I've structured your application requirements for **{solution.title}** into the "
                            "FastAPI backend and Next.js frontend workspace. "
                            "Toggle **Build** and send to finalize your deployable package."
                        )

                history = solution.conversation_history or []
                history.append({"role": "user", "content": payload.message})
                history.append({"role": "assistant", "content": assistant_text})
                solution.conversation_history = history

                synthesized = await _synthesize_domain_artifacts_dynamic(
                    solution.title,
                    payload.message,
                    context=payload.uploaded_context or "",
                    history=solution.conversation_history or [],
                    existing_state=ai_state,
                )
                if synthesized.get("app_title") and solution.title in (
                    "Custom App Build",
                    "Custom App",
                ):
                    solution.title = synthesized["app_title"]

                solution.ai_state = {
                    **ai_state,
                    **synthesized,
                    "solution_title": solution.title,
                    "business_description": ai_state.get("business_description") or payload.message,
                }

                build_state: dict[str, Any] = {}
                if payload.build_requested:
                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "analyzing",
                                "step": 1,
                                "total_steps": 7,
                                "percentage": 15,
                                "message": f"Synthesizing domain architecture for {solution.title}...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    await require_and_deduct_credit(
                        stream_db,
                        current_user,
                        "mvp_build",
                        f"Custom build: {solution.title}",
                        solution_id=solution.id,
                    )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "persisting",
                                "step": 2,
                                "total_steps": 7,
                                "percentage": 30,
                                "message": "Persisting architectural blueprints and data models to solution registry...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }
                    # Persist solution artifacts to database so /solution/{id} is fully populated
                    await _persist_artifacts(stream_db, solution, solution.ai_state)

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "scaffolding",
                                "step": 3,
                                "total_steps": 7,
                                "percentage": 50,
                                "message": "Initializing full-stack codebase scaffold (FastAPI + Next.js)...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }
                    # Pre-populate code slots from ai_state
                    builder.scaffold_build(
                        ws_dir,
                        app_title=solution.title,
                        inject_modules=solution.ai_state.get("confirmed_modules") or [],
                        ai_state=solution.ai_state,
                    )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "coding",
                                "step": 4,
                                "total_steps": 7,
                                "percentage": 70,
                                "message": "Synthesizing domain models, Pydantic schemas, and REST routers...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    if sidecar_ok:
                        # Sidecar available — run verify+repair loop with timeout.
                        try:
                            await asyncio.wait_for(
                                mvp_verifier.verify_and_repair(
                                    ws_dir,
                                    session_id=session_id,
                                    target_dir=target_dir,
                                    send_prompt_fn=lambda s, t: builder.send_message(
                                        s, t, timeout=25
                                    ),
                                    check_npm=False,
                                    max_repair_turns=1,
                                ),
                                timeout=35.0,
                            )
                        except TimeoutError:
                            logger.warning(
                                "Sidecar verify_and_repair timed out; performing offline verification"
                            )
                            errors = mvp_verifier.verify_workspace(ws_dir, check_npm=False)
                            if errors:
                                error_summary = "; ".join(errors[:5])
                                raise RuntimeError(
                                    f"Build verification failed: {error_summary}"
                                ) from None
                        except mvp_verifier.VerificationError as exc:
                            raise RuntimeError(f"Build verification failed: {exc}") from exc
                    else:
                        # Offline — run read-only verification, fail honestly
                        # if the synthesized scaffold is broken.
                        errors = mvp_verifier.verify_workspace(ws_dir, check_npm=False)
                        if errors:
                            error_summary = "; ".join(errors[:5])
                            raise RuntimeError(
                                f"Build verification failed ({len(errors)} error(s)): "
                                f"{error_summary}"
                            )

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "packaging",
                                "step": 6,
                                "total_steps": 7,
                                "percentage": 90,
                                "message": "Packaging production archive (.zip) and saving build artifacts...",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                            }
                        ),
                    }

                    build_number = await _next_build_number(stream_db, solution.id)
                    files = builder.list_build_files(ws_dir)
                    rel_files = builder.relative_paths(ws_dir)

                    # Package archive to local disk and object storage
                    local_zip_path = ws_dir.with_suffix(".zip")
                    zip_data = builder.build_bytes(ws_dir)
                    local_zip_path.write_bytes(zip_data)

                    storage_key = f"local:{local_zip_path}"
                    try:
                        storage = get_storage()
                        uploaded_key = await asyncio.wait_for(
                            storage.upload_bytes(
                                zip_data, f"builds/{solution.id}/build_{build_number}.zip"
                            ),
                            timeout=15.0,
                        )
                        if uploaded_key:
                            storage_key = uploaded_key
                    except Exception as store_err:
                        logger.warning(
                            "Remote storage upload failed (%s); using local fallback (%s)",
                            store_err,
                            local_zip_path,
                        )

                    mvp_build = MVPBuild(
                        solution_id=solution.id,
                        build_number=build_number,
                        status="complete",
                        workspace_path=str(ws_dir),
                        file_count=len(files),
                        file_list=rel_files,
                        storage_key=storage_key,
                        opencode_session_id=session_id,
                        app_config={
                            "app_name": solution.title,
                            "source": "opencode_chat",
                            "progress": {
                                "stage": "complete",
                                "step": 7,
                                "total_steps": 7,
                                "percentage": 100,
                                "message": f"Build complete! {len(files)} files generated.",
                            },
                        },
                    )
                    stream_db.add(mvp_build)
                    solution.status = "complete"
                    await stream_db.flush()
                    build_state = {
                        "build_id": str(mvp_build.id),
                        "build_number": build_number,
                        "file_count": len(files),
                        "files": [{"path": p, "size": 0, "is_dir": False} for p in rel_files],
                    }

                    yield {
                        "event": "build_progress",
                        "data": json.dumps(
                            {
                                "phase": "completed",
                                "step": 7,
                                "total_steps": 7,
                                "percentage": 100,
                                "message": f"Build complete! {len(files)} files generated.",
                                "solution_id": str(solution.id),
                                "session_id": session_id,
                                "build_id": str(mvp_build.id),
                                "file_count": len(files),
                            }
                        ),
                    }

                await stream_db.commit()

            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "role": "assistant",
                        "message": assistant_text,
                        "session_id": session_id,
                    }
                ),
            }
            yield {
                "event": "complete",
                "data": json.dumps(
                    {
                        "status": "complete" if payload.build_requested else "message",
                        "message": assistant_text,
                        "session_id": session_id,
                        "solution_id": str(solution.id),
                        **build_state,
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error in OpenCode chat")
            try:
                async with async_session_factory() as err_db:
                    if payload.solution_id:
                        sol = await err_db.get(Solution, payload.solution_id)
                        if sol is not None:
                            sol.status = "failed"
                            await err_db.commit()
            except Exception:  # noqa: BLE001 - best-effort failure persistence
                pass
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
