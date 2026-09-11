"""
AI Solution Builder — Full-Stack Code Synthesizer Agent Node

The terminal production node (Section 5 of the implementation plan):
turns the validated ER diagram, API spec, and wireframes into a mounted,
working application — real DDL for dynamic schema provisioning plus module
manifests consumed by the Workable System Runtime Engine.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import CODE_SYNTHESIZER_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def code_synthesizer_node(state: DiscoveryState) -> dict[str, Any]:
    """Synthesize executable schema DDL and workable module manifests."""
    logger.info("Full-Stack Code Synthesizer: generating workable system")

    llm = get_llm(temperature=0.1, max_tokens=8192, state=state)

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])
    er_artifact = state.get("er_diagram")
    api_artifact = state.get("api_spec")
    er: dict[str, Any] = er_artifact.get("content", {}) if er_artifact else {}
    api_spec: dict[str, Any] = api_artifact.get("content", {}) if api_artifact else {}
    wireframes = state.get("wireframes") or []

    messages = [
        SystemMessage(content=CODE_SYNTHESIZER_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Modules: {json.dumps(modules)}
ER Entities: {json.dumps(er.get("entities", []), default=str)}
API Endpoints: {json.dumps(api_spec.get("endpoints", []), default=str)}
Wireframe Modules: {json.dumps([wf.get("module") for wf in wireframes if isinstance(wf, dict)], default=str)}"""
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
        logger.error("Failed to parse code synthesizer response")
        result = {
            "generated_schema": {"declarative": {"tables": []}, "ddl": ""},
            "workable_modules": [],
            "code_manifest": {"framework": "FastAPI + Next.js", "tree": [], "stack_version": "1.0"},
        }

    generated_schema = result.get("generated_schema", {"declarative": {"tables": []}, "ddl": ""})
    workable_modules = result.get("workable_modules", [])
    code_manifest = result.get("code_manifest", {})

    return {
        "generated_schema": {
            "artifact_type": "database_schema",
            "title": "Executable Database Schema",
            "content": {
                "declarative": generated_schema.get("declarative", {}),
                "ddl": generated_schema.get("ddl", ""),
            },
            "content_text": generated_schema.get("ddl", ""),
        },
        "workable_modules": workable_modules,
        "code_manifest": code_manifest,
        "workable_ready": True,
        "current_agent": "code_synthesizer",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "code_synthesizer",
                "type": "code_complete",
                "data": {
                    "table_count": len(generated_schema.get("declarative", {}).get("tables", [])),
                    "workable_module_count": len(workable_modules),
                    "manifest_tree": code_manifest.get("tree", []),
                },
            }
        ],
    }
