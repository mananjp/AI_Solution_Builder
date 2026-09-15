"""
AI Solution Builder — Blueprint Generator Agent Node

Assembles all agent outputs into a complete solution blueprint
with roadmap, effort estimation, risks, and success metrics.
"""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import BLUEPRINT_GENERATOR_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 15  # seconds — stay under Groq 6k TPM


def _fallback(message: str) -> dict[str, Any]:
    """Return minimal blueprint so the pipeline can still complete."""
    logger.warning("Blueprint Generator using fallback: %s", message)
    result = {
        "executive_summary": f"Blueprint generation incomplete: {message}",
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
        "agent_messages": [],
    }


async def blueprint_generator_node(state: DiscoveryState) -> dict[str, Any]:
    """Synthesize a complete solution blueprint from all prior outputs."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    logger.info("Blueprint Generator: assembling final blueprint")

    try:
        llm = get_llm(temperature=0.3, max_tokens=2048)
    except Exception as exc:
        logger.error("Blueprint Generator: failed to get LLM — %s", exc)
        return _fallback(f"LLM init failed: {exc}")

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])

    # Gather summaries from prior agents — aggressively truncate to stay under Groq 8k TPM
    hld_artifact = state.get("hld")
    er_artifact = state.get("er_diagram")
    hld_summary = json.dumps(hld_artifact.get("content", {}) if hld_artifact else {}, default=str)[
        :400
    ]
    er_summary = json.dumps(er_artifact.get("content", {}) if er_artifact else {}, default=str)[
        :400
    ]
    wireframe_count = len(state.get("wireframes") or [])
    biz_desc = state.get("business_description", "")[:300]

    messages = [
        SystemMessage(content=BLUEPRINT_GENERATOR_SYSTEM),
        HumanMessage(
            content=f"""Business: {biz_desc}
Industry: {state.get("industry", "general")}
Modules: {json.dumps(modules)[:300]}
Architecture: {hld_summary}
DB Entities: {er_summary}
Wireframes: {wireframe_count} screens"""
        ),
    ]

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("Blueprint Generator: LLM call failed — %s", exc)
        return _fallback(f"LLM call failed: {exc}")

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.error("Blueprint Generator: failed to parse JSON response")
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
