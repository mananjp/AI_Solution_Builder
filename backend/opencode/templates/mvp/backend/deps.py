from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.security import decode_token
from .db import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user_id(token: str) -> str | None:
    """Resolve the subject (user id) from a Bearer token."""
    sub = decode_token(token)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sub


CurrentUser = Annotated[str | None, Depends(get_current_user_id)]