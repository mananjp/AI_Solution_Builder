"""
AI Solution Builder — Solutions Architect Agent Node

Generates HLD (High-Level Design) and LLD (Low-Level Design)
based on confirmed requirements and module list.
"""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import SOLUTIONS_ARCHITECT_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 15  # seconds — stay under Groq 6k TPM

_EMPTY_HLD: dict[str, Any] = {"title": "High-Level Design", "components": [], "system_overview": ""}
_EMPTY_LLD: dict[str, Any] = {"title": "Low-Level Design", "modules": []}


def _fallback(message: str) -> dict[str, Any]:
    """Return a minimal HLD+LLD so downstream nodes can still run."""
    logger.warning("Solutions Architect using fallback: %s", message)
    empty_hld = {**_EMPTY_HLD, "raw_text": message}
    empty_lld = {**_EMPTY_LLD, "raw_text": message}
    return {
        "hld": {
            "artifact_type": "hld",
            "title": "High-Level Design",
            "content": empty_hld,
            "content_text": json.dumps(empty_hld, indent=2),
        },
        "lld": {
            "artifact_type": "lld",
            "title": "Low-Level Design",
            "content": empty_lld,
            "content_text": json.dumps(empty_lld, indent=2),
        },
        "current_agent": "solutions_architect",
        "status": "generating",
        "agent_messages": [],
    }


async def solutions_architect_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate system architecture (HLD + LLD) for confirmed modules."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    logger.info("Solutions Architect Agent: generating architecture")

    try:
        llm = get_llm(temperature=0.2, max_tokens=2048)
    except Exception as exc:
        logger.error("Solutions Architect: failed to get LLM — %s", exc)
        return _fallback(f"LLM init failed: {exc}")

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])

    messages = [
        SystemMessage(content=SOLUTIONS_ARCHITECT_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Confirmed Modules to Build: {json.dumps(modules)}
Stakeholders: {json.dumps(state.get("stakeholders", []))}
Pain Points: {json.dumps(state.get("pain_points", []))}"""
        ),
    ]

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("Solutions Architect: LLM call failed — %s", exc)
        return _fallback(f"LLM call failed: {exc}")

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.error("Solutions Architect: failed to parse JSON response")
        result = {
            "hld": {"title": "Architecture", "raw_text": response.content},
            "lld": {"title": "Detailed Design", "raw_text": response.content},
        }

    hld_data = result.get("hld", {})
    lld_data = result.get("lld", {})

    return {
        "hld": {
            "artifact_type": "hld",
            "title": hld_data.get("title", "High-Level Design"),
            "content": hld_data,
            "content_text": json.dumps(hld_data, indent=2),
        },
        "lld": {
            "artifact_type": "lld",
            "title": lld_data.get("title", "Low-Level Design"),
            "content": lld_data,
            "content_text": json.dumps(lld_data, indent=2),
        },
        "current_agent": "solutions_architect",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "solutions_architect",
                "type": "architecture_complete",
                "data": {
                    "hld_title": hld_data.get("title", "HLD"),
                    "lld_title": lld_data.get("title", "LLD"),
                },
            }
        ],
    }
