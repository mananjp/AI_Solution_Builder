"""
AI Solution Builder — Business Recommendation Agent Node

Activates when the user hasn't specified systems to build.
Classifies the business and proposes relevant modules from the Industry Template Library.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import BUSINESS_RECOMMENDATION_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.templates import GENERIC_TEMPLATE, INDUSTRY_TEMPLATES
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def business_recommendation_node(state: DiscoveryState) -> dict[str, Any]:
    """Recommend software modules based on business classification."""
    logger.info("Business Recommendation Agent: generating recommendations")

    industry = state.get("industry", "general")

    # Check if we have a template for this industry
    template = INDUSTRY_TEMPLATES.get(industry)

    if template:
        logger.info(f"Using template for industry: {industry}")
        return {
            "recommended_modules": template["recommended_modules"],
            "requires_confirmation": True,
            "current_agent": "business_recommendation",
            "status": "recommending",
            "agent_messages": state.get("agent_messages", [])
            + [
                {
                    "agent": "business_recommendation",
                    "type": "recommendation",
                    "data": {
                        "industry": industry,
                        "modules": template["recommended_modules"],
                        "explanation": f"Based on your {industry.replace('_', ' ')} business, here are the recommended systems.",
                    },
                }
            ],
        }

    # Fallback: use LLM for classification and recommendation
    llm = get_llm(temperature=0.3, max_tokens=2048)

    messages = [
        SystemMessage(content=BUSINESS_RECOMMENDATION_SYSTEM),
        HumanMessage(
            content=f"""Business Description: {state.get("business_description", "")}
Industry (pre-classified): {industry}
Business Size: {state.get("business_size", "unknown")}
Business Stage: {state.get("business_stage", "unknown")}
Pain Points: {", ".join(state.get("pain_points", []))}"""
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
        logger.warning("Failed to parse recommendation response, using generic template")
        result = {
            "industry": industry,
            "recommended_modules": GENERIC_TEMPLATE["recommended_modules"],
            "explanation": "Here are some commonly needed systems for your business.",
        }

    return {
        "recommended_modules": result.get(
            "recommended_modules", GENERIC_TEMPLATE["recommended_modules"]
        ),
        "requires_confirmation": True,
        "current_agent": "business_recommendation",
        "status": "recommending",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "business_recommendation",
                "type": "recommendation",
                "data": result,
            }
        ],
    }
