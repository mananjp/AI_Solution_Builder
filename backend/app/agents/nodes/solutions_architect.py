"""
AI Solution Builder — Solutions Architect Agent Node

Generates HLD (High-Level Design) and LLD (Low-Level Design)
based on confirmed requirements and module list.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import SOLUTIONS_ARCHITECT_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def solutions_architect_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate system architecture (HLD + LLD) for confirmed modules."""
    logger.info("Solutions Architect Agent: generating architecture")

    llm = get_llm(temperature=0.2, max_tokens=8192)

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

    response = await llm.ainvoke(messages)

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        result = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse architecture response")
        result = {
            "hld": {"title": "Architecture", "raw_text": response.content},
            "lld": {"title": "Detailed Design", "raw_text": response.content},
        }

    hld_data = result.get("hld", {})
    lld_data = result.get("lld", {})

    decisions = result.get("decisions", [])
    if not decisions:
        decisions = [
            {
                "id": "dec-arch-1",
                "topic": "Architecture Pattern",
                "choice": hld_data.get("architecture_pattern", "Modular Service Architecture"),
                "rationale": "Balances rapid deployment velocity with clear domain boundaries and future horizontal scaling.",
                "alternatives": ["Pure Monolith", "Complex Microservices"],
                "assumptions": ["Workload demands rapid time-to-market with tenant isolation"],
                "evidence": [
                    {"source": "user_msg", "excerpt": state.get("business_description", "")[:100]}
                ],
                "confidence": 0.9,
                "impact": "high",
            }
        ]
    hld_data["decisions"] = decisions

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
        "decisions": state.get("decisions", []) + decisions,
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
