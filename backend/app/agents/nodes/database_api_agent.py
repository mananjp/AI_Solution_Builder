"""
AI Solution Builder — Database & API Agent Node

Generates ER diagrams, PostgreSQL DDL schemas, and API endpoint specifications.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import DATABASE_API_AGENT_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def database_api_agent_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate ER diagram, DDL schema, and API spec."""
    logger.info("Database & API Agent: generating schema and API spec")

    llm = get_llm(temperature=0.1, max_tokens=8192)

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])
    hld_artifact = state.get("hld")
    lld_artifact = state.get("lld")
    hld: dict[str, Any] = hld_artifact.get("content", {}) if hld_artifact else {}
    lld: dict[str, Any] = lld_artifact.get("content", {}) if lld_artifact else {}

    messages = [
        SystemMessage(content=DATABASE_API_AGENT_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Modules: {json.dumps(modules)}
HLD Components: {json.dumps(hld.get("components", []), default=str)}
LLD Modules: {json.dumps(lld.get("modules", []), default=str)}"""
        ),
    ]

    response = await llm.ainvoke(messages)

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        result = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse DB/API response")
        result = {"er_diagram": {"entities": []}, "schema_ddl": "", "api_endpoints": []}

    return {
        "er_diagram": {
            "artifact_type": "er_diagram",
            "title": "Entity-Relationship Diagram",
            "content": result.get("er_diagram", {}),
            "content_text": json.dumps(result.get("er_diagram", {}), indent=2),
        },
        "database_schema": {
            "artifact_type": "database_schema",
            "title": "Database Schema (PostgreSQL DDL)",
            "content": {"ddl": result.get("schema_ddl", "")},
            "content_text": result.get("schema_ddl", ""),
        },
        "api_spec": {
            "artifact_type": "api_spec",
            "title": "API Specification",
            "content": {"endpoints": result.get("api_endpoints", [])},
            "content_text": json.dumps(result.get("api_endpoints", []), indent=2),
        },
        "current_agent": "database_api_agent",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "database_api_agent",
                "type": "schema_complete",
                "data": {
                    "entity_count": len(result.get("er_diagram", {}).get("entities", [])),
                    "endpoint_count": len(result.get("api_endpoints", [])),
                },
            }
        ],
    }
