"""
AI Solution Builder — Feature Advisor Agent Node (P1)

Recommends high-value domain-specific features with clear ROI rationales
based on the industry template library and competitive benchmarks.
"""

import json
import logging
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import DiscoveryState
from app.agents.templates import INDUSTRY_TEMPLATES
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

FEATURE_ADVISOR_SYSTEM = """You are a Product Strategy and ROI Advisor.
Your role is to recommend differentiating, high-impact features that standard MVP creators miss.
Each recommendation MUST include:
- Feature name and description
- Competitive benchmark: ("Competitors in this space usually have X")
- Measurable ROI rationale: ("Reduces customer churn by ~15%", "Automates 10h/week of manual billing")
- Implementation complexity: "low" | "medium" | "high"

Respond ONLY with valid JSON in this structure:
{
  "suggested_features": [
    {
      "id": "feat-1",
      "name": "Feature Name",
      "description": "Short explanation",
      "competitive_benchmark": "Leading products in X provide Y",
      "roi_rationale": "Expected business impact",
      "complexity": "low" | "medium" | "high",
      "category": "retention" | "monetization" | "automation" | "experience"
    }
  ]
}
"""


async def feature_advisor_node(state: DiscoveryState) -> dict[str, Any]:
    """Recommend high-value features with competitive ROI rationales."""
    logger.info("Feature Advisor Agent: starting analysis")
    llm = get_llm(temperature=0.3, max_tokens=3000)

    industry = state.get("industry", "general")
    business_desc = state.get("business_description", state.get("user_message", ""))
    template_info = INDUSTRY_TEMPLATES.get(industry, {})

    prompt = f"""Business Description: {business_desc}
Industry: {industry}
Industry Baseline Modules: {template_info.get("recommended_modules", [])}
Current Pain Points: {state.get("pain_points", [])}
"""

    messages = [
        SystemMessage(content=FEATURE_ADVISOR_SYSTEM),
        HumanMessage(content=prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        data = json.loads(content.strip())
    except Exception as err:
        logger.warning(
            "Failed to parse feature advisor response, using template heuristics: %s", err
        )
        # Template-based fallback
        suggested = []
        raw_modules = template_info.get("recommended_modules", [])
        modules: list[Any] = raw_modules if isinstance(raw_modules, list) else []
        for m in modules[:4]:
            if isinstance(m, dict):
                module_name = str(m.get("module", ""))
                reason = str(m.get("reason", ""))
                suggested.append(
                    {
                        "id": f"feat-{uuid.uuid4().hex[:4]}",
                        "name": module_name.replace("_", " ").title(),
                        "description": reason,
                        "competitive_benchmark": f"Standard for {industry.replace('_', ' ')} solutions",
                        "roi_rationale": f"Improves operations and address: {reason}",
                        "complexity": "medium",
                        "category": "automation",
                    }
                )
        if not suggested:
            suggested = [
                {
                    "id": f"feat-{uuid.uuid4().hex[:4]}",
                    "name": "Automated Notification System",
                    "description": "Multi-channel SMS, Email, and WhatsApp notifications",
                    "competitive_benchmark": "Standard customer engagement baseline",
                    "roi_rationale": "Reduces no-show and missed action rates by up to 25%",
                    "complexity": "low",
                    "category": "experience",
                }
            ]
        data = {"suggested_features": suggested}

    features = data.get("suggested_features", [])
    return {
        "suggested_features": features,
        "current_agent": "feature_advisor",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "feature_advisor",
                "type": "features_advised",
                "data": {
                    "count": len(features),
                    "features": [f.get("name") for f in features],
                },
            }
        ],
    }
