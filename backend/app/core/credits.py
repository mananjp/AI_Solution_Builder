"""
AI Solution Builder — Credit Metering Service (Section 9 / 13)

Gates every generation, regeneration, and export action against the
organization's available credits, deducts on execution, and records a
credit_transactions ledger row for audit/billing.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.credit import CreditTransaction
from app.models.user import User

logger = logging.getLogger(__name__)

CREDIT_COSTS = {
    "generation": settings.GENERATION_CREDIT_COST,
    "regeneration": settings.REGENERATION_CREDIT_COST,
    "export": settings.EXPORT_CREDIT_COST,
    "mvp_build": settings.MVP_BUILD_CREDIT_COST,
}


def action_cost(action_type: str) -> int:
    return CREDIT_COSTS.get(action_type, settings.GENERATION_CREDIT_COST)


async def check_credits(db: AsyncSession, org_id: str) -> int:
    """Return the org's remaining credit count."""
    from app.models.organization import Organization

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org.credits_remaining or 0


async def require_and_deduct_credit(
    db: AsyncSession,
    user: User,
    action_type: str,
    description: str = "",
    solution_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Verify and deduct credits for a metered action.

    Raises HTTP 402 when the org has insufficient credits. Returns the new
    balance alongside the deduction record.
    """
    from app.models.organization import Organization

    action = "regeneration" if action_type in ("regeneration", "regenerate") else action_type
    cost = action_cost(action)
    if cost <= 0:
        return {"credits_remaining": None, "deducted": 0, "cost": 0}

    org_result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.plan))
        .where(Organization.id == user.org_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None or org.credits_remaining is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.credits_remaining < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": f"Insufficient credits — this action costs {cost}, balance is {org.credits_remaining}. Upgrade your plan to continue.",
                "details": [
                    {
                        "cost": cost,
                        "balance": org.credits_remaining,
                        "plan": org.plan.name if org.plan else "free",
                    }
                ],
            },
        )

    org.credits_remaining -= cost

    tx = CreditTransaction(
        org_id=org.id,
        action_type=action,
        credits_used=-cost,  # negative = consumption; top-ups are positive
        description=description or f"{action} action",
        solution_id=solution_id,
    )
    db.add(tx)
    logger.info(
        "Credit deducted org=%s action=%s cost=%s remaining=%s",
        org.id,
        action,
        cost,
        org.credits_remaining,
    )
    return {"credits_remaining": org.credits_remaining, "deducted": cost, "cost": cost}


async def credit_usage(db: AsyncSession, org_id: str, limit: int = 100) -> dict[str, Any]:
    """Aggregate metering summary for the /billing/credits endpoint."""
    total = await db.execute(
        select(func.coalesce(-func.sum(CreditTransaction.credits_used), 0)).where(
            CreditTransaction.org_id == org_id,
            CreditTransaction.credits_used < 0,
        )
    )
    spent_total = total.scalar() or 0

    by_type_rows = await db.execute(
        select(
            CreditTransaction.action_type,
            func.sum(CreditTransaction.credits_used).label("total"),
        )
        .where(CreditTransaction.org_id == org_id, CreditTransaction.credits_used < 0)
        .group_by(CreditTransaction.action_type)
    )
    by_type = {action: int(-(value or 0)) for action, value in by_type_rows.all()}

    recent_rows = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.org_id == org_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
    )
    recent = [
        {
            "id": tx.id,
            "action_type": tx.action_type,
            "credits_used": tx.credits_used,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx in recent_rows.scalars().all()
    ]

    remaining = await check_credits(db, org_id)
    return {
        "balance": remaining,
        "total_spent": int(spent_total),
        "by_action": by_type,
        "recent_transactions": recent,
    }
