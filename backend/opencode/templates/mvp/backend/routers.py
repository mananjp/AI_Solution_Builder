"""API routers.

The MVP Build Agent adds one CRUD router per module here and wires them
into the app in main.py. A health router is provided as the base.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from .core.config import settings
from .deps import SessionDep

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


# __ROUTER_INSERTION_POINT__
