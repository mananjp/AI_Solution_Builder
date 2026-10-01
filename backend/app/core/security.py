"""AI Solution Builder - Authentication & Security.

Auth0 is the sole identity provider. This module validates Auth0-issued RS256
access tokens against the tenant's JWKS and resolves them to a local `User` row,
then exposes the FastAPI dependencies that guard every route.

Why the local `User` row still exists: roles, organisation membership, the
encrypted per-user deploy-secret vault and Postgres RLS all key off a stable
local UUID. The Auth0 `sub` identifies the *identity*; the `User` row owns the
*authorisation state*. Keeping that split means revoking a role in SUTRA does
not require an Auth0 change, and deactivating a user takes effect on the very
next request rather than at token expiry.

Passwords, local token minting, and the hand-rolled GitHub/Google OAuth flow
were removed. Credentials, MFA, social login, breached-password detection and
session revocation are Auth0's job now.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    MissingRequiredClaimError,
    PyJWKClientError,
    PyJWTError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)

# ── Bearer Token Scheme ──────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)

# `PyJWKClient` owns the JWKS cache, the `kid` lookup and the refresh cooldown,
# including refreshing once when it meets an unknown `kid`. Re-implementing
# that here would only be a worse copy, so the client does it.
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """Lazily build the JWKS client. Raising here is caught as a 500 by design:
    a misconfigured AUTH0_DOMAIN should not masquerade as a 401."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    domain = settings.auth0_domain
    if not domain or ".auth0.com" not in domain:
        raise RuntimeError(
            "AUTH0_DOMAIN is not configured, so the API cannot verify bearer tokens. "
            "Set it to the bare tenant domain, e.g. 'your-tenant.us.auth0.com', and restart."
        )

    _jwks_client = jwt.PyJWKClient(
        f"https://{domain}/.well-known/jwks.json",
        cache_keys=True,
        lifespan=settings.AUTH0_JWKS_CACHE_SECONDS,
        timeout=10.0,
        cooldown_duration=30,
    )
    return _jwks_client


async def warm_jwks() -> None:
    """Prime the signing-key cache off the event loop at startup.

    Optional by design: a failure here logs and continues, because the per-token
    path can still fetch lazily. Warming it up front keeps the first request
    after a deploy or a cold start off the blocking fetch path.
    """
    if not settings.AUTH0_ENABLED or not settings.auth0_domain:
        return

    import anyio.to_thread

    try:
        client = _get_jwks_client()
        await anyio.to_thread.run_sync(client.fetch_data)
        logger.info("Auth0 JWKS cache warmed for %s", settings.auth0_issuer)
    except Exception as exc:
        logger.warning("Could not warm the Auth0 JWKS cache (%s); will retry lazily", exc)


def reset_jwks_cache() -> None:
    """Drop the cached client. Used by tests that point at a different tenant."""
    global _jwks_client
    _jwks_client = None


def _unauthorized(detail: str) -> HTTPException:
    """401 with the challenge header clients need to trigger a re-login."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


def decode_token(token: str) -> dict[str, Any]:
    """Validate an Auth0 access token and return its claims.

    Checks, in order: the token is well-formed, the algorithm is RS256, the
    signature matches a key from the tenant JWKS, the issuer is this tenant,
    the audience is this API, and it has not expired.

    Pinning `algorithms=["RS256"]` and rejecting anything else in the header is
    what closes the algorithm-confusion hole: a token re-signed HS256 using the
    published RSA public key as the shared secret is refused before the key is
    ever used.
    """
    if not settings.AUTH0_ENABLED:
        raise _unauthorized("Authentication is disabled on this server")

    issuer = settings.auth0_issuer
    if not issuer or issuer == "https:///":
        raise RuntimeError(
            "AUTH0_DOMAIN is not configured; cannot validate bearer tokens. "
            "Set it in the environment and restart."
        )

    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise _unauthorized("Malformed authorization token") from exc

    if header.get("alg") != "RS256":
        raise _unauthorized(f"Unsupported token algorithm: {header.get('alg')!r}")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    except PyJWKClientError as exc:
        raise _unauthorized("Token signing key is not recognised") from exc
    except Exception as exc:  # network, TLS, malformed JWKS
        raise RuntimeError(f"Unable to retrieve Auth0 signing keys: {exc}") from exc

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=issuer,
            leeway=settings.AUTH0_LEEWAY_SECONDS,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except ExpiredSignatureError:
        raise _unauthorized("Token has expired") from None
    except InvalidAudienceError:
        raise _unauthorized("Token audience is not accepted by this API") from None
    except InvalidIssuerError:
        raise _unauthorized("Token was issued by an untrusted issuer") from None
    except MissingRequiredClaimError as exc:
        raise _unauthorized(f"Token missing required claim: {exc}") from None
    except InvalidSignatureError:
        raise _unauthorized("Token signature verification failed") from None
    except PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc


def _extract_email_from_claims(claims: dict[str, Any]) -> str | None:
    """Extract an email address from standard or custom namespaced Auth0 claims."""
    for key in ("email", "upn", "preferred_username", "unique_name"):
        val = claims.get(key)
        if isinstance(val, str) and "@" in val:
            return val.strip().lower()

    for key, val in claims.items():
        if isinstance(val, str) and "@" in val and (key.endswith("/email") or key.endswith(":email")):
            return val.strip().lower()

    return None


async def _fetch_userinfo(token: str) -> dict[str, Any]:
    """Fetch user profile from Auth0's /userinfo endpoint using the bearer token.

    Auth0 API access tokens do not include profile claims (email, name) by default.
    Querying /userinfo with the access token is the standard OIDC way to obtain profile details.
    """
    domain = settings.auth0_domain
    if not domain:
        return {}
    url = f"https://{domain}/userinfo"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data
            else:
                logger.warning("Auth0 /userinfo returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Could not reach Auth0 /userinfo (%s); proceeding with token claims", exc)
    return {}



async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve the bearer token to a local `User`.

    On first sight of an Auth0 identity a `User` row, an `Organization` and a
    default `Workspace` are provisioned, so a successful Auth0 login can never
    land the caller on a page that then 500s for want of an org.
    """
    from app.models.user import User

    if credentials is None or not credentials.credentials:
        # Dev-only: let the UI be exercised without a working Auth0 tenant.
        # `DEV_AUTH_BYPASS` is rejected at boot when APP_ENV='production', so this
        # branch is unreachable in a deployed environment.
        if settings.APP_ENV != "production" and settings.DEV_AUTH_BYPASS:
            # Named distinctly from `user` below: binding `user` here would make
            # mypy infer it as `User`, and the normal path assigns a
            # `User | None` from `scalar_one_or_none()`.
            dev_user = await _get_or_create_dev_user(db)
            request.state.user_sub = str(dev_user.id)
            request.state.org_id = str(dev_user.org_id) if dev_user.org_id else None
            return dev_user
        raise _unauthorized("Not authenticated")

    claims = decode_token(credentials.credentials)
    subject = claims.get("sub")
    if not subject:
        raise _unauthorized("Token missing subject claim")

    issuer = str(claims.get("iss") or settings.auth0_issuer)
    email = _extract_email_from_claims(claims)

    result = await db.execute(
        select(User).where(
            User.auth_provider == "auth0",
            User.auth_issuer == issuer,
            User.provider_user_id == subject,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        # If user is not yet provisioned and email or name is missing,
        # fetch user profile from Auth0's /userinfo endpoint.
        if not email or not (claims.get("name") or claims.get("given_name")):
            userinfo = await _fetch_userinfo(credentials.credentials)
            if userinfo:
                if not email and userinfo.get("email"):
                    email = str(userinfo["email"]).strip().lower()
                for k, v in userinfo.items():
                    if k not in claims:
                        claims[k] = v

        user = await _provision_user(
            db=db,
            claims=claims,
            issuer=issuer,
            subject=str(subject),
            email=email,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Keep the locally stored profile and role in step with Auth0 on every
    # request. This is what makes an Auth0-side role change take effect
    # immediately rather than after the user re-authenticates.
    changed = False
    name = str(claims.get("name") or claims.get("given_name") or "").strip()
    if name and name != user.full_name:
        user.full_name = name[:255]
        changed = True
    if email and email != user.email:
        user.email = email[:255]
        changed = True
    if claims.get("email_verified") is True and not user.email_verified:
        user.email_verified = True
        changed = True

    role = _role_from_claims(claims, email, user.role)
    if role != user.role:
        user.role = role
        changed = True

    if changed:
        try:
            await db.commit()
            await db.refresh(user)
        except Exception:
            # A profile sync failure must not reject an otherwise valid
            # request; the next one will retry.
            await db.rollback()
            logger.exception("Failed to sync Auth0 profile for user %s", user.id)

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


DEV_BYPASS_ISSUER = "dev://auth-bypass"
DEV_BYPASS_SUBJECT = "dev-bypass"


async def _get_or_create_dev_user(db: AsyncSession) -> User:
    """Resolve the synthetic identity used when `DEV_AUTH_BYPASS` is on.

    This returns a genuine persisted user, not a stub: it reuses
    `_provision_user` so the bypassed session owns a real Organization and a
    default Workspace. That matters because almost every route derives its
    tenancy from `user.org_id`; handing back a detached object would just trade
    these 401s for 500s.
    """
    from app.models.user import User

    result = await db.execute(
        select(User).where(
            User.auth_provider == "auth0",
            User.auth_issuer == DEV_BYPASS_ISSUER,
            User.provider_user_id == DEV_BYPASS_SUBJECT,
        )
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    return await _provision_user(
        db=db,
        claims={
            "sub": DEV_BYPASS_SUBJECT,
            "email": settings.DEV_AUTH_BYPASS_EMAIL,
            "name": "Dev User",
            "email_verified": True,
        },
        issuer=DEV_BYPASS_ISSUER,
        subject=DEV_BYPASS_SUBJECT,
        email=settings.DEV_AUTH_BYPASS_EMAIL,
    )


def _role_from_claims(claims: dict[str, Any], email: str | None, current: str) -> str:
    """Resolve the effective SUTRA role.

    The namespaced custom claim is authoritative when present, because that is
    the only place an operator can express a deliberate grant without touching
    the database. `AUTH0_ADMIN_EMAILS` is a bootstrap for the very first admin,
    since an empty tenant has no roles in its Action yet.
    """
    raw = claims.get(settings.AUTH0_ROLE_CLAIM)
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, list):
        for candidate in raw:
            role = str(candidate).strip().lower()
            if role in ROLE_PERMISSIONS or role in ("admin", "superadmin"):
                return role

    # app_metadata.roles is the usual place an Action writes structured roles.
    metadata = claims.get("app_metadata")
    if isinstance(metadata, dict):
        meta_roles = metadata.get("roles")
        if isinstance(meta_roles, str):
            meta_roles = [meta_roles]
        if isinstance(meta_roles, list):
            for candidate in meta_roles:
                role = str(candidate).strip().lower()
                if role in ROLE_PERMISSIONS or role in ("admin", "superadmin"):
                    return role

    if email and email in settings.auth0_admin_emails:
        return "admin"

    return current or "member"


async def _provision_user(
    *,
    db: AsyncSession,
    claims: dict[str, Any],
    issuer: str,
    subject: str,
    email: str | None,
) -> User:
    """Create the local User + Organization + Workspace for a first-time login."""
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.workspace import Workspace

    if not email:
        clean_sub = subject.split("|")[-1] if "|" in subject else subject
        email = f"user_{clean_sub[:16]}@auth0.local"
        logger.info("Auth0 profile has no email claim; assigned fallback %s for sub=%s", email, subject)

    name = (
        str(claims.get("name") or "").strip()
        or str(claims.get("given_name") or "").strip()
        or email.split("@")[0]
    )

    free_plan = None
    try:
        from app.services.billing import get_or_create_free_plan

        free_plan = await get_or_create_free_plan(db)
    except Exception:
        logger.exception("Could not attach a free plan to new Auth0 user %s", subject)

    org_name = f"{name}'s Workspace"
    org = Organization(
        name=org_name,
        plan_id=getattr(free_plan, "id", None),
        credits_remaining=200,
    )
    db.add(org)
    await db.flush()

    workspace = Workspace(
        name="Primary Workspace",
        org_id=org.id,
    )
    db.add(workspace)

    user = User(
        email=email[:255],
        full_name=name[:255],
        hashed_password=None,
        auth_provider="auth0",
        auth_issuer=issuer,
        provider_user_id=subject,
        email_verified=bool(claims.get("email_verified")),
        is_anonymous=False,
        role="owner",
        org_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("Provisioned Auth0 user sub=%s email=%s org=%s", subject, email, org.id)
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
