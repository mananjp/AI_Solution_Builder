"""
AI Solution Builder — Auth API Routes

Register, login, and current-user endpoints.
Creates an Organization automatically on registration.
"""

import urllib.parse
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.secrets import encrypt_secret
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.credit import Plan
from app.models.organization import Organization
from app.models.user import User
from app.schemas import (
    AnonymousAuthResponse,
    SocialProvidersResponse,
    TokenResponse,
    UpgradeAnonymousRequest,
    UserLogin,
    UserRegister,
    UserResponse,
    UserSettingsUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/providers", response_model=SocialProvidersResponse)
async def get_auth_providers() -> SocialProvidersResponse:
    """Return the list of configured social OAuth providers and guest mode status.

    Only presents providers where both client ID and secret are configured in the
    environment, avoiding broken redirect buttons.
    """
    providers: list[str] = []
    if settings.AUTH_GITHUB_CLIENT_ID and settings.AUTH_GITHUB_CLIENT_SECRET:
        providers.append("github")
    if settings.AUTH_GOOGLE_CLIENT_ID and settings.AUTH_GOOGLE_CLIENT_SECRET:
        providers.append("google")
    return SocialProvidersResponse(
        providers=providers,
        allow_anonymous=settings.ALLOW_ANONYMOUS_AUTH,
    )


@router.post(
    "/anonymous", response_model=AnonymousAuthResponse, status_code=status.HTTP_201_CREATED
)
async def create_anonymous_user(db: AsyncSession = Depends(get_db)) -> AnonymousAuthResponse:
    """Issue a throwaway anonymous guest identity with a low credit ceiling for demo exploration."""
    if not settings.ALLOW_ANONYMOUS_AUTH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anonymous demo access is disabled",
        )

    free_plan_result = await db.execute(select(Plan).where(Plan.name == "free"))
    free_plan = free_plan_result.scalar_one_or_none()
    if not free_plan:
        free_plan = Plan(name="free", monthly_credits=200, max_workable_systems=1, price_usd=0)
        db.add(free_plan)
        await db.flush()

    guest_id = uuid.uuid4().hex[:8]
    org = Organization(
        name=f"Guest Workspace ({guest_id})",
        plan_id=free_plan.id,
        credits_remaining=settings.ANONYMOUS_CREDITS,  # None = unlimited credits
    )
    db.add(org)
    await db.flush()

    guest_email = f"guest_{guest_id}@guest.local"
    user = User(
        email=guest_email,
        full_name="Guest Architect",
        hashed_password=None,
        role="guest",
        auth_provider="anonymous",
        is_anonymous=True,
        org_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return AnonymousAuthResponse(
        access_token=token,
        token_type="bearer",
        is_anonymous=True,
        credits_remaining=settings.ANONYMOUS_CREDITS,
        user=UserResponse.model_validate(user),
    )


@router.post("/upgrade-anonymous", response_model=UserResponse)
async def upgrade_anonymous_account(
    payload: UpgradeAnonymousRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Upgrade an anonymous guest account into a permanent account without losing blueprints."""
    if not current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current account is already a permanent account",
        )

    # Check if target email already exists
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    current_user.email = payload.email
    current_user.full_name = payload.full_name
    current_user.hashed_password = hash_password(payload.password)
    current_user.is_anonymous = False
    current_user.auth_provider = "local"

    # Also rename organization if org_name is provided and bump credits to full free plan (200)
    if current_user.org_id:
        org = await db.get(Organization, current_user.org_id)
        if org:
            if payload.org_name:
                org.name = payload.org_name
            if org.credits_remaining is not None and org.credits_remaining < 200:
                org.credits_remaining = 200

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str) -> dict[str, str]:
    """Return the OAuth authorization URL for the requested provider."""
    state = uuid.uuid4().hex
    if provider == "github":
        if not (settings.AUTH_GITHUB_CLIENT_ID and settings.AUTH_GITHUB_CLIENT_SECRET):
            raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")
        params = {
            "client_id": settings.AUTH_GITHUB_CLIENT_ID,
            "scope": "read:user user:email",
            "state": state,
        }
        url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
        return {"authorization_url": url}
    elif provider == "google":
        if not (settings.AUTH_GOOGLE_CLIENT_ID and settings.AUTH_GOOGLE_CLIENT_SECRET):
            raise HTTPException(status_code=400, detail="Google OAuth is not configured")
        redirect_uri = f"{settings.FRONTEND_URL}/api/v1/auth/oauth/google/callback"
        params = {
            "client_id": settings.AUTH_GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return {"authorization_url": url}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider}")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Exchange authorization code, fetch user details, issue JWT, and redirect to frontend."""
    email: str | None = None
    full_name: str = "Architect"
    provider_user_id: str | None = None

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        if provider == "github":
            if not (settings.AUTH_GITHUB_CLIENT_ID and settings.AUTH_GITHUB_CLIENT_SECRET):
                raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")
            token_resp = await http_client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.AUTH_GITHUB_CLIENT_ID,
                    "client_secret": settings.AUTH_GITHUB_CLIENT_SECRET,
                    "code": code,
                },
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=400, detail="Failed to retrieve GitHub access token"
                )

            user_resp = await http_client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            user_data = user_resp.json()
            provider_user_id = str(user_data.get("id"))
            full_name = user_data.get("name") or user_data.get("login") or "GitHub Architect"
            email = user_data.get("email")

            if not email:
                emails_resp = await http_client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
                if emails_resp.status_code == 200:
                    for em in emails_resp.json():
                        if em.get("primary") and em.get("verified"):
                            email = em.get("email")
                            break
                        elif not email:
                            email = em.get("email")

        elif provider == "google":
            if not (settings.AUTH_GOOGLE_CLIENT_ID and settings.AUTH_GOOGLE_CLIENT_SECRET):
                raise HTTPException(status_code=400, detail="Google OAuth is not configured")
            redirect_uri = f"{settings.FRONTEND_URL}/api/v1/auth/oauth/google/callback"
            token_resp = await http_client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.AUTH_GOOGLE_CLIENT_ID,
                    "client_secret": settings.AUTH_GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=400, detail="Failed to retrieve Google access token"
                )

            user_resp = await http_client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_data = user_resp.json()
            provider_user_id = str(user_data.get("id"))
            full_name = user_data.get("name") or "Google Architect"
            email = user_data.get("email")

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider}")

    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from OAuth provider")

    # Find existing user by provider_user_id or email
    user_query = await db.execute(
        select(User).where((User.provider_user_id == provider_user_id) | (User.email == email))
    )
    user = user_query.scalar_one_or_none()

    if not user:
        free_plan_result = await db.execute(select(Plan).where(Plan.name == "free"))
        free_plan = free_plan_result.scalar_one_or_none()
        if not free_plan:
            free_plan = Plan(name="free", monthly_credits=200, max_workable_systems=1, price_usd=0)
            db.add(free_plan)
            await db.flush()

        org = Organization(
            name=f"{full_name}'s Workspace", plan_id=free_plan.id, credits_remaining=200
        )
        db.add(org)
        await db.flush()

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=None,
            auth_provider=provider,
            provider_user_id=provider_user_id,
            is_anonymous=False,
            role="owner",
            org_id=org.id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if not user.provider_user_id and provider_user_id:
            user.provider_user_id = provider_user_id
            await db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    frontend_target = f"{settings.FRONTEND_URL}/auth/callback?token={token}"
    return RedirectResponse(url=frontend_target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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
    free_plan = free_plan_result.scalars().first()
    if not free_plan:
        free_plan = Plan(name="free", monthly_credits=200, max_workable_systems=1, price_usd=0)
        db.add(free_plan)
        await db.flush()

    # Check if an organization with org_name already exists
    org_result = await db.execute(
        select(Organization)
        .where(Organization.name == payload.org_name)
        .order_by(Organization.created_at.desc())
    )
    org = org_result.scalars().first()

    if not org:
        org = Organization(name=payload.org_name, plan_id=free_plan.id, credits_remaining=200)
        db.add(org)
        await db.flush()
        user_role = "owner"
    else:
        from sqlalchemy import func

        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.org_id == org.id)
        )
        user_count = user_count_result.scalar() or 0
        user_role = "owner" if user_count == 0 else "member"

    # Create user
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=user_role,
        org_id=org.id,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent registration with the same email lost the race against
        # the unique constraint after the pre-check passed — surface 409, not 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None

    # Generate JWT
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return a JWT."""

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if (
        not user
        or not user.hashed_password
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    user_email = (user.email or "").lower()
    if (user.is_anonymous or "demo" in user_email or "guest" in user_email) and user.org_id:
        org = await db.get(Organization, user.org_id)
        if org and org.credits_remaining is not None:
            org.credits_remaining = None
            await db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the currently authenticated user's profile."""
    user_email = (current_user.email or "").lower()
    if (
        current_user.is_anonymous or "demo" in user_email or "guest" in user_email
    ) and current_user.org_id:
        org = await db.get(Organization, current_user.org_id)
        if org and org.credits_remaining is not None:
            org.credits_remaining = None
            await db.commit()
    return current_user


@router.api_route("/me/settings", methods=["PATCH", "POST"], response_model=dict[str, bool])
async def update_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Persist deploy credentials (e.g. GitHub PAT) on the user's profile."""
    from sqlalchemy.orm.attributes import flag_modified

    settings = dict(current_user.settings or {})
    if payload.github_token is not None:
        token = payload.github_token.strip()
        if token:
            settings["github_token"] = encrypt_secret(token)
        else:
            settings.pop("github_token", None)
    if payload.render_api_key is not None:
        api_key = payload.render_api_key.strip()
        if api_key:
            settings["render_api_key"] = encrypt_secret(api_key)
        else:
            settings.pop("render_api_key", None)
    if payload.vercel_token is not None:
        token = payload.vercel_token.strip()
        if token:
            settings["vercel_token"] = encrypt_secret(token)
        else:
            settings.pop("vercel_token", None)
    current_user.settings = settings
    flag_modified(current_user, "settings")
    await db.commit()
    return {"updated": True}
