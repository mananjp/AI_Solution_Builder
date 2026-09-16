"""
AI Solution Builder — Billing & Monetization API
(Section 13 of the implementation plan)

Plans, credit metering, and transaction ledgers.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.credit import CreditTransaction
from app.models.organization import Organization
from app.models.user import User

router = APIRouter(prefix="/billing", tags=["Billing & Credits"])


class TopupRequest(BaseModel):
    amount: int  # Number of credits to purchase


@router.get("/plans")
async def get_plans(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """List available subscription plans."""
    return [
        {
            "id": "free",
            "name": "Free Tier",
            "price_usd": 0,
            "monthly_credits": 1000,
            "max_workable_systems": 1,
            "features": [
                "1 Workable System",
                "1,000 monthly credits",
                "Community Support",
                "Standard exports (JSON, Markdown)",
            ],
        },
        {
            "id": "pro",
            "name": "Professional",
            "price_usd": 49,
            "monthly_credits": 10000,
            "max_workable_systems": 5,
            "features": [
                "5 Workable Systems",
                "10,000 monthly credits",
                "Priority Groq 120B inference",
                "Deployable Code ZIP + CI/CD",
                "BPMN Process Modeler",
            ],
        },
        {
            "id": "enterprise",
            "name": "Enterprise Scale",
            "price_usd": 299,
            "monthly_credits": 100000,
            "max_workable_systems": 50,
            "features": [
                "Unlimited Workable Systems",
                "100,000 monthly credits",
                "Dedicated Schema Isolation",
                "One-Click Deployer",
                "Audit Logging & SLA",
            ],
        },
    ]


@router.get("/usage")
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get current organization credit balance and usage."""
    org_result = await db.execute(
        select(Organization)
        .options(joinedload(Organization.plan))
        .where(Organization.id == current_user.org_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    plan = org.plan
    plan_name = plan.name if plan else "free"
    monthly_limit = plan.monthly_credits if plan else 0
    balance = org.credits_remaining

    unlimited = balance is None
    if unlimited:
        plan_name = "Unlimited"
        monthly_limit = None
        credits_used = None
    else:
        credits_used = max(0, monthly_limit - balance)

    return {
        "org_id": str(org.id),
        "plan_name": plan_name,
        "monthly_limit": monthly_limit,
        "current_balance": balance,
        "credits_used": credits_used,
    }


@router.get("/transactions")
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get credit transaction audit log for organization."""
    tx_res = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.org_id == current_user.org_id)
        .order_by(desc(CreditTransaction.created_at))
        .limit(20)
    )
    transactions = tx_res.scalars().all()

    return [
        {
            "id": str(t.id),
            "amount": t.credits_used,
            "action": t.action_type,
            "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transactions
    ]


@router.post("/topup")
async def topup_credits(
    payload: TopupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Top up credits for the organization."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    org_result = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    # Unlimited accounts keep a NULL balance; top-ups are meaningless for them.
    if org.credits_remaining is not None:
        org.credits_remaining += payload.amount

    tx = CreditTransaction(
        org_id=current_user.org_id,
        credits_used=payload.amount,  # positive = balance added
        action_type="credit_purchase",
        description=f"Purchased {payload.amount:,} AI credits",
    )
    db.add(tx)
    await db.commit()

    return {
        "status": "success",
        "added": payload.amount,
        "message": f"Successfully credited {payload.amount:,} AI credits",
    }
