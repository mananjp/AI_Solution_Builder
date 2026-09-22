"""
AI Solution Builder — Requirement Gap & Compliance Agent Node (P1)

Analyzes business requirements against an enterprise checklist (NFRs, compliance,
security, audit, integrations) and identifies missing or suggested requirements
plus prioritized open questions explaining "why it matters".
"""

import json
import logging
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import DiscoveryState, Requirement
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

REQUIREMENT_GAP_SYSTEM = """You are an Enterprise Solutions Analyst specializing in gap analysis and compliance.
Your job is to examine the user's business description, pain points, and current solutions, and identify:
1. Missing Non-Functional Requirements (NFRs): scalability, availability/SLA, backup/DR, offline access, latency.
2. Compliance & Regulatory Gaps: DPDP Act (India), GDPR (EU), data residency, consent management, audit trails, data retention.
3. Architecture Gaps: RBAC/permissions, payment reconciliation, notifications (SMS/WhatsApp/Email), reporting.
4. Top 5 Prioritized Open Questions: Clarifications the user must answer before architecture, each with 'why_it_matters'.

Respond ONLY with valid JSON in this structure:
{
  "requirements": [
    {
      "id": "req-1",
      "kind": "functional" | "nfr" | "compliance" | "integration",
      "text": "Description of requirement",
      "status": "stated" | "inferred" | "missing" | "suggested",
      "priority": "must" | "should" | "could",
      "evidence": [{"source": "user_msg", "excerpt": "..."}]
    }
  ],
  "open_questions": [
    {
      "id": "q-1",
      "question": "Question text?",
      "category": "compliance" | "payments" | "scale" | "security",
      "why_it_matters": "Business/technical justification...",
      "suggested_answers": ["Option A", "Option B"]
    }
  ],
  "assumptions_log": [
    {
      "id": "asm-1",
      "topic": "compliance",
      "assumption": "Assumed standard DPDP compliance needed for Indian customer data",
      "impact": "high"
    }
  ]
}
"""


async def requirement_gap_node(state: DiscoveryState) -> dict[str, Any]:
    """Identify missing requirements, NFRs, compliance gaps, and prioritized questions."""
    logger.info("Requirement Gap Agent: starting analysis")
    llm = get_llm(temperature=0.2, max_tokens=3000)

    user_msg = state.get("user_message", "")
    description = state.get("business_description", user_msg)
    industry = state.get("industry", "general")
    pain_points = state.get("pain_points", [])
    solutions = state.get("identified_solutions", [])

    prompt = f"""Business Description: {description}
Industry: {industry}
Pain Points: {pain_points}
Identified Solutions: {solutions}
Uploaded Context: {state.get("uploaded_context", "")[:1000]}
"""

    messages = [
        SystemMessage(content=REQUIREMENT_GAP_SYSTEM),
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
            "Failed to parse requirement gap response, using structured defaults: %s", err
        )
        data = {
            "requirements": [
                {
                    "id": f"req-{uuid.uuid4().hex[:4]}",
                    "kind": "compliance",
                    "text": "Data protection and user consent management (DPDP/GDPR)",
                    "status": "missing",
                    "priority": "must",
                    "evidence": [{"source": "inferred", "excerpt": f"Industry: {industry}"}],
                },
                {
                    "id": f"req-{uuid.uuid4().hex[:4]}",
                    "kind": "nfr",
                    "text": "Role-based access control (RBAC) and audit trail logging",
                    "status": "missing",
                    "priority": "must",
                    "evidence": [{"source": "inferred", "excerpt": "Enterprise baseline"}],
                },
            ],
            "open_questions": [
                {
                    "id": f"q-{uuid.uuid4().hex[:4]}",
                    "question": "What customer data privacy and regulatory standards (e.g. DPDP, GDPR, HIPAA) apply to your users?",
                    "category": "compliance",
                    "why_it_matters": "Determines encryption at rest, consent capture flows, and data residency architecture.",
                    "suggested_answers": [
                        "DPDP Act (India)",
                        "GDPR (Europe)",
                        "Standard commercial privacy",
                    ],
                },
                {
                    "id": f"q-{uuid.uuid4().hex[:4]}",
                    "question": "What payment channels and tax invoicing (GST / VAT) are required?",
                    "category": "payments",
                    "why_it_matters": "Affects webhook reconciliation, ledger structures, and checkout UX.",
                    "suggested_answers": [
                        "UPI + Cards (Razorpay/Stripe)",
                        "Offline / Cash on Delivery",
                        "None / Internal tool",
                    ],
                },
            ],
            "assumptions_log": [
                {
                    "id": f"asm-{uuid.uuid4().hex[:4]}",
                    "topic": "security",
                    "assumption": "Assumed multi-tenant data isolation with RBAC enforcement",
                    "impact": "high",
                }
            ],
        }

    raw_reqs: list[Requirement] = data.get("requirements", [])
    open_qs = data.get("open_questions", [])[:5]  # Cap at 5 prioritized questions
    assumptions = data.get("assumptions_log", [])

    return {
        "requirements": raw_reqs,
        "open_questions": open_qs,
        "assumptions_log": assumptions,
        "current_agent": "requirement_gap",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "requirement_gap",
                "type": "gap_analysis_complete",
                "data": {
                    "missing_count": len(
                        [r for r in raw_reqs if r.get("status") in ("missing", "suggested")]
                    ),
                    "questions_count": len(open_qs),
                },
            }
        ],
    }
