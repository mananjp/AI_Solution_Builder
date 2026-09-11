"""
AI Solution Builder — Auth API Routes

Register, login, and current-user endpoints.
Creates an Organization automatically on registration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.credit import Plan
from app.models.organization import Organization
from app.models.user import User
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Register a new user and create their organization."""

    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Get or create the free plan
    free_plan_result = await db.execute(select(Plan).where(Plan.name == "free"))
    free_plan = free_plan_result.scalar_one_or_none()
    if not free_plan:
        free_plan = Plan(name="free", monthly_credits=200, max_workable_systems=1, price_usd=0)
        db.add(free_plan)
        await db.flush()

    # Create organization
    org = Organization(name=payload.org_name, plan_id=free_plan.id, credits_remaining=200)
    db.add(org)
    await db.flush()

    # Create user
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="admin",
        org_id=org.id,
    )
    db.add(user)
    await db.flush()

    # Generate JWT
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return a JWT."""

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user
