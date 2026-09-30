"""
AI Solution Builder - Auth API Routes

Auth0 owns authentication. This module no longer issues tokens, stores
passwords, or speaks to GitHub/Google directly: the browser completes Universal
Login against Auth0 and presents the resulting access token as a bearer token,
which `app.core.security.get_current_user` validates.

What remains here is the local-authorisation surface - who the caller is, their
role, and the encrypted deploy credentials they have stored. The public
`/config` endpoint exists so the frontend can discover the tenant it should
authenticate against without hardcoding a second copy of the domain.
"""

from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.database import get_db
from app.core.secrets import encrypt_secret
from app.core.security import get_current_user
from app.models.user import User
from app.schemas import UserResponse, UserSettingsUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/config")
async def get_auth_config() -> dict[str, object]:
    """Tell the browser which Auth0 tenant to authenticate against.

    Unauthenticated by necessity: the frontend calls it before it has a token.
    It exposes only the tenant domain and the role-claim name, both of which
    are public identifiers that are already visible in the OIDC discovery
    document. No client secret and no audience is returned.
    """
    return {
        "enabled": settings.AUTH0_ENABLED,
        "domain": settings.auth0_domain,
        "issuer": settings.auth0_issuer,
        "role_claim": settings.AUTH0_ROLE_CLAIM,
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the caller's profile, role and organisation."""
    return current_user


@router.api_route("/me/settings", methods=["PATCH", "POST"], response_model=dict[str, bool])
async def update_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Persist deploy credentials (e.g. GitHub PAT) on the user's profile.

    Empty strings clear a stored secret rather than storing an empty one, so
    the "remove my key" gesture works and does not leave a decoy behind.
    """
    stored = dict(current_user.settings or {})

    for field in ("github_token", "render_api_key", "vercel_token"):
        value = getattr(payload, field, None)
        if value is None:
            continue
        cleaned = value.strip()
        if cleaned:
            stored[field] = encrypt_secret(cleaned)
        else:
            stored.pop(field, None)

    current_user.settings = stored
    flag_modified(current_user, "settings")
    await db.commit()
    return {"updated": True}


@router.get("/logout", include_in_schema=False)
async def logout_redirect() -> RedirectResponse:
    """Send the browser to Auth0's logout endpoint.

    There is deliberately no local logout state to clear: the API holds no
    session, because it never issued the token. The frontend calls this so the
    Auth0 SSO session is destroyed too, otherwise the next person to use the
    machine is silently signed back in.
    """
    if not settings.auth0_domain:
        return RedirectResponse(url="/login")

    return_to = quote(settings.FRONTEND_URL, safe="")
    return RedirectResponse(
        url=f"https://{settings.auth0_domain}/v2/logout?client_id=public&returnTo={return_to}"
    )
