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

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.credit import CreditTransaction
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
    # Sum up transactions
    tx_res = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.org_id == current_user.org_id)
        .order_by(desc(CreditTransaction.created_at))
    )
    transactions = tx_res.scalars().all()

    total_balance = sum(t.credits_used for t in transactions)
    # Give default starting credits if brand new org
    if total_balance == 0 and not transactions:
        total_balance = 8500

    return {
        "org_id": current_user.org_id,
        "plan_name": "Professional",
        "monthly_limit": 10000,
        "current_balance": max(0, total_balance),
        "credits_used": max(0, 10000 - total_balance),
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

    if not transactions:
        # Provide sample ledger if fresh instance
        return [
            {
                "id": "demo-tx-1",
                "amount": 10000,
                "action": "plan_renewal",
                "description": "Monthly Professional Plan Allocation",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "id": "demo-tx-2",
                "amount": -200,
                "action": "generate_solution",
                "description": "Full Swarm Solution Synthesis",
                "created_at": "2026-09-10T12:00:00Z",
            },
        ]

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

    tx = CreditTransaction(
        org_id=current_user.org_id,
        credits_used=payload.amount,
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
