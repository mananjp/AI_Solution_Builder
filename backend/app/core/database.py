"""
AI Solution Builder — Async Database Engine

Async SQLAlchemy 2.0 with asyncpg driver for PostgreSQL.
Provides session factory and dependency injection for FastAPI routes.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URL for asyncpg compatibility (e.g. for Neon DB).

    - Translates scheme: postgres:// or postgresql:// -> postgresql+asyncpg://
    - Translates query parameter: sslmode=... -> ssl=... (asyncpg rejects sslmode)
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if "sslmode=" in url:
        url = url.replace("sslmode=", "ssl=")
    return url


# ── Engine & Session Factory ──────────────────────
engine = create_async_engine(
    normalize_database_url(settings.DATABASE_URL),
    echo=settings.APP_ENV == "development",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

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
