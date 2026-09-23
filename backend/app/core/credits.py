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


async def check_credits(db: AsyncSession, org_id: str) -> int | None:
    """Return the org's remaining credit count.

    Returns ``None`` when the org has unlimited credits (NULL balance).
    """
    from app.models.organization import Organization

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org.credits_remaining


async def require_and_deduct_credit(
    db: AsyncSession,
    user: User,
    action_type: str,
    description: str = "",
    solution_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Verify and deduct credits for a metered action.

    Orgs with a NULL balance are treated as unlimited and bypass deduction.
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
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Demo/guest account or NULL balance = unlimited credits; skip metering entirely.
    user_email = (getattr(user, "email", "") or "").lower()
    org_name = (getattr(org, "name", "") or "").lower()
    is_demo = (
        getattr(user, "is_anonymous", False)
        or "demo" in user_email
        or "guest" in user_email
        or "demo" in org_name
        or "guest" in org_name
        or org.credits_remaining is None
    )
    if is_demo:
        logger.info(
            "Credit gating skipped (unlimited) user=%s org=%s action=%s cost=%s",
            user_email,
            org.id,
            action,
            cost,
        )
        return {"credits_remaining": None, "deducted": 0, "cost": cost}

    assert org.credits_remaining is not None
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


async def refund_credit(
    db: AsyncSession,
    user: User | None = None,
    action_type: str = "",
    cost: int | None = None,
    description: str = "",
    solution_id: UUID | str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Refund credits for a failed metered action and log a reversal transaction.

    Orgs with a NULL balance are unlimited and skip refunding. Either ``user``
    or ``org_id`` must be supplied (``org_id`` lets background jobs refund
    without a live request user).
    """
    from app.models.organization import Organization

    org_identifier = org_id or (user.org_id if user else None)
    if org_identifier is None:
        raise ValueError("refund_credit requires either a user or an org_id")

    action = "regeneration" if action_type in ("regeneration", "regenerate") else action_type
    refund_amount = cost if cost is not None else action_cost(action)
    if refund_amount <= 0:
        return {"credits_remaining": None, "refunded": 0}

    org_result = await db.execute(
        select(Organization).where(Organization.id == org_identifier)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.credits_remaining is not None:
        org.credits_remaining += refund_amount

    tx = CreditTransaction(
        org_id=org.id,
        action_type=f"{action}_refund",
        credits_used=refund_amount,  # positive = balance restored
        description=description or f"Refund for failed {action}",
        solution_id=solution_id,
    )

    db.add(tx)
    logger.info(
        "Credit refunded org=%s action=%s amount=%s remaining=%s",
        org.id,
        action,
        refund_amount,
        org.credits_remaining,
    )
    return {"credits_remaining": org.credits_remaining, "refunded": refund_amount}


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
