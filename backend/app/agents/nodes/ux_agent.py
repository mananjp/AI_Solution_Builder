"""
AI Solution Builder — UX Agent Node

Generates wireframe specifications, navigation flows,
dashboard layouts, and design tokens.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import UX_AGENT_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def ux_agent_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate wireframe specs and navigation flows."""
    logger.info("UX Agent: generating wireframes")

    llm = get_llm(temperature=0.4, max_tokens=8192)

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])
    hld_artifact = state.get("hld")
    hld: dict[str, Any] = hld_artifact.get("content", {}) if hld_artifact else {}

    messages = [
        SystemMessage(content=UX_AGENT_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Modules: {json.dumps(modules)}
Architecture Summary: {json.dumps(hld.get("system_overview", ""), default=str)}
Stakeholders: {json.dumps(state.get("stakeholders", []))}"""
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
        logger.error("Failed to parse UX response")
        result = {"wireframes": [], "navigation": {}, "design_tokens": {}}

    wireframe_artifacts = []
    for wf in result.get("wireframes", []):
        wireframe_artifacts.append(
            {
                "artifact_type": "wireframe",
                "title": f"Wireframes — {wf.get('module', 'Unknown')}",
                "content": wf,
                "content_text": json.dumps(wf, indent=2),
            }
        )

    return {
        "wireframes": wireframe_artifacts,
        "current_agent": "ux_agent",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "ux_agent",
                "type": "wireframes_complete",
                "data": {
                    "screen_count": sum(
                        len(wf.get("screens", [])) for wf in result.get("wireframes", [])
                    ),
                    "design_tokens": result.get("design_tokens", {}),
                },
            }
        ],
    }
