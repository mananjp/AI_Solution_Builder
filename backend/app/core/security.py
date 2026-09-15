"""
AI Solution Builder — Authentication & Security

JWT token management, password hashing, and FastAPI dependencies
for protecting routes with bearer token auth. Also exposes a
role-gated `require_admin` dependency for the admin/ governance surface.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

if TYPE_CHECKING:
    from app.models.user import User

# ── Password Hashing ─────────────────────────────
# Use a backend that works consistently in local development environments
# without the bcrypt wheel incompatibility seen on newer Python builds.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ── Bearer Token Scheme ──────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)

DEV_DEMO_EMAIL = "demo@aibuilder.example"
DEV_DEMO_PASSWORD = "DemoPass123!"


def hash_password(password: str) -> str:
    """Hash a plaintext password using the configured passlib backend."""
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against the current hashed password."""
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


async def ensure_dev_demo_user(db: AsyncSession) -> User | None:
    """Create a seeded demo account for local development if no user exists."""
    if settings.APP_ENV.lower() != "development":
        return None

    from app.models.credit import Plan
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.workspace import Workspace

    user = (await db.execute(select(User).where(User.email == DEV_DEMO_EMAIL))).scalar_one_or_none()
    if user is None:
        plan = (await db.execute(select(Plan).where(Plan.name == "free"))).scalar_one_or_none()
        if plan is None:
            plan = Plan(name="free", monthly_credits=10000, max_workable_systems=3, price_usd=0)
            db.add(plan)
            await db.flush()

        org = (await db.execute(select(Organization).where(Organization.name == "Demo Org"))).scalar_one_or_none()
        if org is None:
            org = Organization(name="Demo Org", plan_id=plan.id, credits_remaining=plan.monthly_credits)
            db.add(org)
            await db.flush()

        user = User(
            email=DEV_DEMO_EMAIL,
            full_name="Demo User",
            hashed_password=hash_password(DEV_DEMO_PASSWORD),
            role="admin",
            org_id=org.id,
        )
        db.add(user)
        await db.flush()

        workspace = (
            await db.execute(
                select(Workspace).where(Workspace.org_id == org.id, Workspace.name == "Demo Workspace")
            )
        ).scalar_one_or_none()
        if workspace is None:
            db.add(
                Workspace(
                    org_id=org.id,
                    name="Demo Workspace",
                    description="Pre-created workspace for local demo use.",
                )
            )

    await db.commit()
    return user


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with the given payload and expiration."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate the current user from JWT.

    Returns the User ORM object if the token is valid. Also attaches the
    user sub and org id to request.state for rate limiting and auditing.
    """
    # Import here to avoid circular imports
    from app.models.user import User

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject claim",
        ) from None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    request.state.user_sub = str(user.id)
    request.state.org_id = str(user.org_id) if user.org_id else None
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that only admits users with an admin role."""

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
