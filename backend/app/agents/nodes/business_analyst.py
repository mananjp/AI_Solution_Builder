"""
AI Solution Builder — Business Analyst Agent Node

Analyzes user input, extracts requirements, scores confidence.
Routes to clarification, recommendation, or blueprint generation.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import BUSINESS_ANALYST_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)


def _fallback(current_message: str, *, confidence: float = 0.5) -> dict[str, Any]:
    """Return a minimal analysis so the pipeline can still route."""
    logger.warning("Business Analyst using fallback (confidence=%.2f)", confidence)
    return {
        "business_description": current_message,
        "industry": "general",
        "business_size": "sme",
        "business_stage": "idea",
        "stakeholders": [],
        "pain_points": [],
        "identified_solutions": [],
        "confidence_score": confidence,
        "clarification_questions": [
            "Could you tell me more about your business and what systems you need?"
        ],
        "analysis_summary": "Analysis was unavailable due to a temporary error.",
        "current_agent": "business_analyst",
        "status": "analyzing",
        "agent_messages": [],
    }


async def business_analyst_node(state: DiscoveryState) -> dict[str, Any]:
    """Analyze user input and extract structured business requirements."""
    logger.info("Business Analyst Agent: starting analysis")

    current_message = state.get("user_message", "")

    try:
        llm = get_llm(temperature=0.3, max_tokens=2048)
    except Exception as exc:
        logger.error("Business Analyst: failed to get LLM — %s", exc)
        return _fallback(current_message)

    # Build conversation context
    messages: list[HumanMessage | SystemMessage] = [SystemMessage(content=BUSINESS_ANALYST_SYSTEM)]

    # Include any uploaded document context
    context_parts = []
    if state.get("uploaded_context"):
        context_parts.append(f"UPLOADED DOCUMENT CONTEXT:\n{state['uploaded_context']}")

    # Include conversation history
    for msg in state.get("conversation_history", []):
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))

    # Current message with context
    if context_parts:
        current_message = "\n\n".join(context_parts) + "\n\nUSER MESSAGE: " + current_message

    messages.append(HumanMessage(content=current_message))

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("Business Analyst: LLM call failed — %s", exc)
        return _fallback(current_message)

    # Parse structured response
    try:
        analysis = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Business Analyst: failed to parse JSON response, using defaults")
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
