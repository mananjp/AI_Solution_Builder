"""
AI Solution Builder — Async Database Engine

Async SQLAlchemy 2.0 with asyncpg driver for PostgreSQL.
Provides session factory and dependency injection for FastAPI routes.
"""

import ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse, parse_qs

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── SSL config for cloud databases (Neon, Supabase, etc.) ──
_connect_args: dict = {}
_clean_url = settings.DATABASE_URL

if not settings.DATABASE_URL.startswith("sqlite"):
    _url = urlparse(settings.DATABASE_URL)
    _query = parse_qs(_url.query)
    if "sslmode" in _query or "ssl" in _query:
        ssl_mode = _query.get("sslmode", _query.get("ssl", ["require"]))[0]
        ssl_ctx = ssl.create_default_context()
        if ssl_mode in ("require", "verify-full", "verify-ca"):
            ssl_ctx.check_hostname = ssl_mode == "verify-full"
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED if ssl_mode in ("verify-full", "verify-ca") else ssl.CERT_NONE
        _connect_args["ssl"] = ssl_ctx

    # Strip query params asyncpg doesn't understand (sslmode, channel_binding)
    _clean_url = settings.DATABASE_URL.split("?")[0]

# ── Engine & Session Factory ──────────────────────
engine_kwargs: dict = {
    "echo": settings.APP_ENV == "development",
    "connect_args": _connect_args or {},
}

if not settings.DATABASE_URL.startswith("sqlite"):
    # Pool settings are appropriate for PostgreSQL (asyncpg) but not for
    # the SQLite aiosqlite driver. Only apply them for non-SQLite URLs.
    engine_kwargs.update({"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True})

engine = create_async_engine(_clean_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ─────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


# ── FastAPI Dependency ────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async database session for use in route handlers."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
