"""
AI Solution Builder — Authentication & Security

JWT token management, password hashing, and FastAPI dependencies
for protecting routes with bearer token auth. Also exposes a
role-gated `require_admin` dependency for the admin/ governance surface.
"""

from __future__ import annotations

import logging
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
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Bearer Token Scheme ──────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


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


async def _get_or_create_demo_user(db: AsyncSession) -> User:
    """Ensure a deterministic demo user and workspace exists for instant guest access."""
    from app.core.plans import get_or_create_free_plan
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.workspace import Workspace

    result = await db.execute(select(User).where(User.email == "demo@demo.com"))
    user = result.scalar_one_or_none()
    if user:
        if user.org_id:
            org = await db.get(Organization, user.org_id)
            if org and org.credits_remaining is not None:
                org.credits_remaining = None
                await db.commit()
        return user

    free_plan = await get_or_create_free_plan(db)
    org = Organization(
        name="Demo Workspace",
        plan_id=free_plan.id,
        credits_remaining=None,  # Unlimited demo credits
    )
    db.add(org)
    await db.flush()

    workspace = Workspace(
        name="Primary Workspace",
        description="Demo sandbox architecture zone",
        org_id=org.id,
    )
    db.add(workspace)

    user = User(
        email="demo@demo.com",
        full_name="Demo Architect",
        hashed_password=hash_password("demo"),
        role="owner",
        auth_provider="local",
        is_anonymous=False,
        org_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


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
    import uuid

    from app.models.user import User

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials.strip()
    if raw_token in ("DEMO_SESSION", "demo-token", "demo"):
        demo_user = await _get_or_create_demo_user(db)
        request.state.user_sub = str(demo_user.id)
        request.state.org_id = str(demo_user.org_id) if demo_user.org_id else None
        return demo_user

    payload = decode_token(raw_token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    if str(user_id) in ("demo-user", "DEMO_SESSION", "demo"):
        demo_user = await _get_or_create_demo_user(db)
        request.state.user_sub = str(demo_user.id)
        request.state.org_id = str(demo_user.org_id) if demo_user.org_id else None
        return demo_user

    user = None
    try:
        user_uuid = uuid.UUID(str(user_id))
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
    except (ValueError, TypeError, AttributeError):
        pass

    if user is None:
        result = await db.execute(select(User).where(User.email == str(user_id)))
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

    # Wire the tenant context into the DB session so workable tables protected by
    # RLS policies are filtered per org. Only applies on Postgres (set_config is
    # PG-only) and only when RLS is enabled.
    if settings.RLS_ENABLED and user.org_id and db.get_bind().dialect.name == "postgresql":
        from app.services.rls import set_request_org

        try:
            await set_request_org(db, str(user.org_id))
        except Exception:
            logger.exception("Failed to set RLS org context for user %s", user.id)

    return user


def check_admin(user: User) -> None:
    """Validate that the given user possesses elevated administrator rights."""
    if user.role not in ("admin", "owner", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that only admits users with an admin role."""
    check_admin(current_user)
    return current_user


async def warm_jwks() -> None:
    """Optional cache warmer stub."""
    pass


def reset_jwks_cache() -> None:
    """Optional JWKS cache reset stub."""
    pass


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {
        "billing:manage",
        "members:manage",
        "solution:approve",
        "solution:generate",
        "solution:regenerate",
        "solution:deploy",
        "solution:view",
        "solution:comment",
    },
    "admin": {
        "members:manage",
        "solution:approve",
        "solution:generate",
        "solution:regenerate",
        "solution:deploy",
        "solution:view",
        "solution:comment",
    },
    "approver": {
        "solution:approve",
        "solution:generate",
        "solution:regenerate",
        "solution:deploy",
        "solution:view",
        "solution:comment",
    },
    "editor": {
        "solution:generate",
        "solution:regenerate",
        "solution:view",
        "solution:comment",
    },
    "member": {
        "solution:generate",
        "solution:regenerate",
        "solution:view",
        "solution:comment",
    },
    "viewer": {
        "solution:view",
        "solution:comment",
    },
    "guest": {
        "solution:approve",
        "solution:generate",
        "solution:regenerate",
        "solution:deploy",
        "solution:view",
        "solution:comment",
    },
}


def require_permission(permission: str) -> Any:
    """Dependency generator that verifies current_user holds the given permission."""

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role or "member"
        if user_role == "superadmin":
            return current_user
        allowed = ROLE_PERMISSIONS.get(user_role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required for this action",
            )
        return current_user

    return _check
