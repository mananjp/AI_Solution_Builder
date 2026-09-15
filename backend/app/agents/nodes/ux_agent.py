"""
AI Solution Builder — UX Agent Node

Generates wireframe specifications, navigation flows,
dashboard layouts, and design tokens.
"""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import UX_AGENT_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 15  # seconds — stay under Groq 6k TPM


def _fallback(message: str) -> dict[str, Any]:
    """Return empty wireframes so downstream nodes can still run."""
    logger.warning("UX Agent using fallback: %s", message)
    return {
        "wireframes": [],
        "current_agent": "ux_agent",
        "status": "generating",
        "agent_messages": [],
    }


async def ux_agent_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate wireframe specs and navigation flows."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    logger.info("UX Agent: generating wireframes")

    try:
        llm = get_llm(temperature=0.4, max_tokens=2048)
    except Exception as exc:
        logger.error("UX Agent: failed to get LLM — %s", exc)
        return _fallback(f"LLM init failed: {exc}")

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

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("UX Agent: LLM call failed — %s", exc)
        return _fallback(f"LLM call failed: {exc}")

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.error("UX Agent: failed to parse JSON response")
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
