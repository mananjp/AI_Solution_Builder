"""
AI Solution Builder — Clarification & Requirement Gap Discovery

Analyzes user prompts, conversation history, and uploaded context to proactively
detect underspecified business logic (pricing models, user roles, catalog items,
workflows) before building, preventing "toy" default builds and aligning with user intent.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ClarificationOption:
    label: str
    value: str
    description: str = ""


@dataclass
class ClarificationQuestion:
    id: str
    field: str
    question: str
    rationale: str
    options: list[dict[str, str]]
    allow_custom: bool = True


def detect_value_gaps(
    prompt: str, ai_state: dict[str, Any] | None = None
) -> list[ClarificationQuestion]:
    """Detect high-impact architectural and product questions for a prompt."""
    text = (prompt or "").lower()
    gaps: list[ClarificationQuestion] = []

    # 1. Commercial / Storefront / Vendor: Missing catalog items or pricing strategy
    is_commercial = any(
        w in text
        for w in (
            "vendor",
            "sell",
            "shop",
            "store",
            "ice cream",
            "icecream",
            "product",
            "menu",
            "catalog",
            "order",
            "pricing",
        )
    )
    has_explicit_prices = bool(
        re.search(
            r"\b(\$|₹|rs\.?|usd|\d+\s*(dollars|rupees|bucks))\b|\bprice[s]?\s*(is|are|of)?\s*\d+",
            text,
        )
    )

    if is_commercial and not has_explicit_prices:
        gaps.append(
            ClarificationQuestion(
                id=str(uuid.uuid4())[:8],
                field="pricing_tier",
                question="What pricing model would you like to launch with?",
                rationale="Determines whether to scaffold fixed prices, tiered variants, or dynamic quotes.",
                options=[
                    {
                        "label": "Fixed Price Catalog",
                        "value": "fixed",
                        "description": "Each item has a set retail price (e.g. $10, $20)",
                    },
                    {
                        "label": "Tiered Subscriptions",
                        "value": "tiered",
                        "description": "Monthly recurring plans (Starter, Pro, Enterprise)",
                    },
                    {
                        "label": "Dynamic Quote / Inquiry",
                        "value": "quote",
                        "description": "Customers request a customized quote on checkout",
                    },
                ],
            )
        )

    # 2. Multi-role vs Single Operator
    has_roles = any(
        w in text
        for w in ("role", "admin", "customer", "member", "trainer", "employee", "patient", "doctor")
    )
    is_management = any(
        w in text for w in ("manage", "system", "portal", "dashboard", "crm", "hrms", "booking")
    )
    if is_management and not has_roles:
        gaps.append(
            ClarificationQuestion(
                id=str(uuid.uuid4())[:8],
                field="access_roles",
                question="Who will be using this application?",
                rationale="Configures tenant permissions and separate admin vs customer navigation views.",
                options=[
                    {
                        "label": "Owner & Customers",
                        "value": "owner_customer",
                        "description": "Customers place requests; owner manages fulfilling them",
                    },
                    {
                        "label": "Internal Team Only",
                        "value": "internal_team",
                        "description": "Private workspace for team members with role-based access",
                    },
                    {
                        "label": "Public Self-Service",
                        "value": "public_self_service",
                        "description": "Open public access with optional account registration",
                    },
                ],
            )
        )

    # 3. Fulfillment / Transaction Flow
    if is_commercial and not any(
        w in text for w in ("pickup", "delivery", "shipping", "digital", "instant")
    ):
        gaps.append(
            ClarificationQuestion(
                id=str(uuid.uuid4())[:8],
                field="fulfillment_mode",
                question="How will orders or bookings be fulfilled?",
                rationale="Customizes the checkout drawer fields and confirmation notification flows.",
                options=[
                    {
                        "label": "Instant In-Store Pickup / Counter",
                        "value": "pickup",
                        "description": "Quick order counter with pickup tokens",
                    },
                    {
                        "label": "Direct Delivery with Address",
                        "value": "delivery",
                        "description": "Collects customer delivery address and phone number",
                    },
                    {
                        "label": "Immediate Digital Access",
                        "value": "digital",
                        "description": "Instant confirmation with digital receipts",
                    },
                ],
            )
        )

    return gaps[:2]  # Cap at 2 high-value questions to minimize user friction


def propose_clarification(prompt: str, ai_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate prompt and return clarification proposals if actionable gaps exist."""
    questions = detect_value_gaps(prompt, ai_state)
    return {
        "has_gaps": len(questions) > 0,
        "questions": [asdict(q) for q in questions],
    }
