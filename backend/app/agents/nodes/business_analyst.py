"""
AI Solution Builder — Business Analyst Agent Node

Analyzes user input, extracts requirements, scores confidence.
Routes to clarification, recommendation, or blueprint generation.
"""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agents.prompts import BUSINESS_ANALYST_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def business_analyst_node(state: DiscoveryState) -> dict[str, Any]:
    """Analyze user input and extract structured business requirements."""
    logger.info("Business Analyst Agent: starting analysis")

    llm = get_llm(temperature=0.3, max_tokens=4096)

    # Build conversation context
    messages: list[BaseMessage] = [SystemMessage(content=BUSINESS_ANALYST_SYSTEM)]

    # Include any uploaded document context
    context_parts = []
    if state.get("uploaded_context"):
        context_parts.append(f"UPLOADED DOCUMENT CONTEXT:\n{state['uploaded_context']}")

    # Include conversation history (both user turns and assistant clarifications)
    for msg in state.get("conversation_history", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))

    # Current message with context
    current_message = state.get("user_message", "")
    if context_parts:
        current_message = "\n\n".join(context_parts) + "\n\nUSER MESSAGE: " + current_message

    messages.append(HumanMessage(content=current_message))

    # Invoke LLM
    response = await llm.ainvoke(messages)

    # Parse structured response
    try:
        # Extract JSON from response (handle markdown code blocks)
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        analysis = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse BA response as JSON, using defaults")
        analysis = {
            "business_description": current_message,
            "industry": "general",
            "business_size": "sme",
            "business_stage": "idea",
            "stakeholders": [],
            "pain_points": [],
            "identified_solutions": [],
            "confidence_score": 0.5,
            "clarification_questions": [
                "Could you tell me more about your business and what systems you need?"
            ],
            "analysis_summary": response.content,
        }

    return {
        "business_description": analysis.get("business_description", ""),
        "industry": analysis.get("industry", "general"),
        "business_size": analysis.get("business_size", "sme"),
        "business_stage": analysis.get("business_stage", "idea"),
        "stakeholders": analysis.get("stakeholders", []),
        "pain_points": analysis.get("pain_points", []),
        "identified_solutions": analysis.get("identified_solutions", []),
        "confidence_score": analysis.get("confidence_score", 0.5),
        "clarification_questions": analysis.get("clarification_questions", []),
        "current_agent": "business_analyst",
        "status": "analyzing",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "business_analyst",
                "type": "analysis_complete",
                "data": {
                    "summary": analysis.get("analysis_summary", "Analysis complete"),
                    "confidence": analysis.get("confidence_score", 0.5),
                    "industry": analysis.get("industry", "general"),
                },
            }
        ],
    }
