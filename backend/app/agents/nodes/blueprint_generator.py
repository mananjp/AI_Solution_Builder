"""
AI Solution Builder — Blueprint Generator Agent Node

Assembles all agent outputs into a complete solution blueprint
with roadmap, effort estimation, risks, and success metrics.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import BLUEPRINT_GENERATOR_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def blueprint_generator_node(state: DiscoveryState) -> dict[str, Any]:
    """Synthesize a complete solution blueprint from all prior outputs."""
    logger.info("Blueprint Generator: assembling final blueprint")

    llm = get_llm(temperature=0.3, max_tokens=8192)

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])

    # Gather summaries from prior agents
    hld_artifact = state.get("hld")
    er_artifact = state.get("er_diagram")
    hld_summary = json.dumps(hld_artifact.get("content", {}) if hld_artifact else {}, default=str)[
        :2000
    ]
    er_summary = json.dumps(er_artifact.get("content", {}) if er_artifact else {}, default=str)[
        :2000
    ]
    wireframe_count = len(state.get("wireframes") or [])

    messages = [
        SystemMessage(content=BLUEPRINT_GENERATOR_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Business Stage: {state.get("business_stage", "idea")}
Modules Being Built: {json.dumps(modules)}
Architecture Summary: {hld_summary}
Database Entities: {er_summary}
Wireframe Screens Generated: {wireframe_count}
Stakeholders: {json.dumps(state.get("stakeholders", []))}
Pain Points: {json.dumps(state.get("pain_points", []))}"""
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
        logger.error("Failed to parse blueprint response")
        result = {
            "executive_summary": response.content,
            "roadmap": {"phases": [], "total_duration": "TBD"},
            "effort_estimation": [],
            "risks": [],
            "success_metrics": [],
            "next_steps": [],
        }

    return {
        "roadmap": {
            "artifact_type": "roadmap",
            "title": "Implementation Roadmap & Blueprint",
            "content": result,
            "content_text": json.dumps(result, indent=2),
        },
        "current_agent": "blueprint_generator",
        "status": "complete",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "blueprint_generator",
                "type": "blueprint_complete",
                "data": {
                    "executive_summary": result.get("executive_summary", ""),
                    "total_duration": result.get("roadmap", {}).get("total_duration", "TBD"),
                    "phase_count": len(result.get("roadmap", {}).get("phases", [])),
                },
            }
        ],
    }
