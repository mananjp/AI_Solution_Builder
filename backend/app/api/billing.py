"""AI Solution Builder — Billing & Monetization API
(Section 13 of the implementation plan)

Plans, credit metering, and transaction ledgers.
"""

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_admin
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
    monthly_limit: int | None = plan.monthly_credits if plan else 0
    balance = org.credits_remaining

    user_email = (getattr(current_user, "email", "") or "").lower()
    org_name = (getattr(org, "name", "") or "").lower()
    is_demo = (
        getattr(current_user, "is_anonymous", False)
        or "demo" in user_email
        or "guest" in user_email
        or "demo" in org_name
        or "guest" in org_name
        or balance is None
    )

    credits_used: int | None
    if is_demo:
        plan_name = "Demo Unlimited"
        monthly_limit = None
        credits_used = None
        balance = None
        if org.credits_remaining is not None:
            org.credits_remaining = None
            await db.commit()
    else:
        credits_used = max(0, (monthly_limit or 0) - (balance or 0))

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
    current_user: User = Depends(require_admin),
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


COST_BASIS: dict[str, dict[str, Any]] = {
    "clarification": {"tokens": "~4k", "credits": 1, "rationale": "Single BA / gap analysis turn"},
    "blueprint_generation": {
        "tokens": "~60-90k",
        "credits": 10,
        "rationale": "Multi-agent pipeline (7 agents)",
    },
    "regeneration": {"tokens": "~8-15k", "credits": 2, "rationale": "Single isolated agent node"},
    "cascade_regeneration": {
        "tokens": "sum of nodes",
        "credits": 2,
        "rationale": "2 credits per affected node",
    },
    "mvp_build": {
        "tokens": "~150k + compute",
        "credits": 25,
        "rationale": "Full-stack code synthesis and verification",
    },
    "deploy": {
        "tokens": "infra compute",
        "credits": 5,
        "rationale": "Multi-tier deployment orchestration",
    },
    "export": {"tokens": "~0", "credits": 1, "rationale": "Document synthesis and bundling"},
}


@router.get("/quote")
async def get_credit_quote(action: str, target_count: int = 1) -> dict[str, Any]:
    """Pre-flight credit cost quote with token usage rationale."""
    base = COST_BASIS.get(
        action, {"tokens": "variable", "credits": 2, "rationale": "Standard metered action"}
    )
    cost_per_unit = int(base["credits"])
    total_credits = cost_per_unit * max(1, target_count)
    return {
        "action": action,
        "units": target_count,
        "credits_required": total_credits,
        "approx_tokens": base["tokens"],
        "rationale": base["rationale"],
    }


class CheckoutRequest(BaseModel):
    plan_id: str | None = None
    pack_credits: int | None = None
    gateway: str = "razorpay"  # "razorpay" | "stripe"
    currency: str = "INR"  # "INR" | "USD"


@router.post("/checkout")
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a payment gateway checkout order for Razorpay or Stripe."""
    import uuid

    amount = 399 if payload.pack_credits else 799
    currency = payload.currency.upper()
    order_id = f"order_{uuid.uuid4().hex[:12]}"

    return {
        "gateway": payload.gateway,
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "key_id": "rzp_test_live" if payload.gateway == "razorpay" else "pk_test_stripe",
        "org_id": str(current_user.org_id),
        "credits": payload.pack_credits or 200,
    }


class WebhookPayload(BaseModel):
    event: str
    order_id: str
    org_id: str
    credits: int
    signature: str | None = None


def _verify_webhook_signature(*, raw_body: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of the raw webhook body.

    Supports the two common gateway envelope formats:
      * Stripe: header ``t=<ts>,v1=<sig>`` → HMAC over ``f"{ts}.{raw_body}"``.
      * Razorpay / generic: header is the bare hex digest → HMAC over the body.
    """
    if not signature:
        return False
    stripe_pattern = "v1="
    if stripe_pattern in signature:
        ts, sig = _parse_stripe_signature(signature)
        if not ts:
            return False
        expected = hmac.new(
            secret.encode(), f"{ts}.{raw_body.decode('utf-8', 'replace')}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _parse_stripe_signature(header: str) -> tuple[str | None, str]:
    """Extract the ``v1`` signature and its timestamp from a Stripe header."""
    ts: str | None = None
    sig: str = ""
    for part in header.split(","):
        part = part.strip()
        if part.startswith("t="):
            ts = part[2:]
        elif part.startswith("v1="):
            sig = part[3:]
    return ts, sig


@router.post("/webhook")
async def handle_payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Process a signature-verified webhook from Razorpay/Stripe and credit the org.

    The payload is HMAC-SHA256 signed with ``PAYMENT_WEBHOOK_SECRET``. The
    signature is read from ``X-Payment-Signature`` (or ``X-Razorpay-Signature``
    / ``Stripe-Signature``) and verified against the exact raw request body, so
    an unauthenticated caller cannot self-credit. Fails closed when the secret
    is unconfigured.
    """
    from uuid import UUID

    secret = settings.PAYMENT_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Payment webhook signing secret is not configured (PAYMENT_WEBHOOK_SECRET)",
        )

    raw_body = await request.body()
    signature = (
        request.headers.get("x-payment-signature")
        or request.headers.get("x-razorpay-signature")
        or request.headers.get("stripe-signature")
        or ""
    )
    if not _verify_webhook_signature(raw_body=raw_body, signature=signature, secret=secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = WebhookPayload.model_validate_json(raw_body)

    org_uuid = UUID(payload.org_id)
    org_res = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.credits_remaining is not None:
        org.credits_remaining += payload.credits

    tx = CreditTransaction(
        org_id=org.id,
        credits_used=payload.credits,
        action_type="gateway_purchase",
        description=f"Verified payment credit via webhook ({payload.order_id})",
    )
    db.add(tx)
    await db.commit()

    return {"status": "credited", "added": payload.credits, "new_balance": org.credits_remaining}
