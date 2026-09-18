"""
AI Solution Builder — Async Database Engine

Async SQLAlchemy 2.0 with asyncpg driver for PostgreSQL.
Provides session factory and dependency injection for FastAPI routes.
"""

import uuid
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── SQLite compatibility: render PostgreSQL-specific types on SQLite ──
# Models use `from sqlalchemy.dialects.postgresql import JSONB, UUID` which
# has no native SQLite DDL. Without this, `Base.metadata.create_all()` fails
# on `sqlite+aiosqlite` with "can't render element of type JSONB".
try:
    from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
    from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(_PG_JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
        return "JSON"

    @compiles(_PG_UUID, "sqlite")
    def _compile_uuid_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
        return "CHAR(36)"

    # SQLite stores UUIDs as plain 32-char hex strings, but the PostgreSQL
    # UUID bind processor calls `.hex` on every non-NULL value. That breaks
    # lookups that pass a string id (e.g. the JWT `sub` claim → `User.id == sub`),
    # raising `'str' object has no attribute 'hex'`. Normalize strings to hex
    # first so they bind identically to stored values.
    _orig_uuid_bind = _PG_UUID.bind_processor

    def _sqlite_uuid_bind_processor(self, dialect):  # type: ignore[no-untyped-def]
        process = _orig_uuid_bind(self, dialect)
        if process is None or dialect.name != "sqlite":
            return process

        def wrapped(value):
            if value is None:
                return None
            if isinstance(value, str):
                try:
                    return uuid.UUID(value).hex
                except (ValueError, AttributeError, TypeError):
                    return value
            return process(value)

        return wrapped

    _PG_UUID.bind_processor = _sqlite_uuid_bind_processor
except Exception:
    pass


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URL for asyncpg compatibility (e.g. for Neon DB).

    - Translates scheme: postgres:// or postgresql:// -> postgresql+asyncpg://
    - Translates query parameter: sslmode=... -> ssl=... (asyncpg rejects sslmode)
    - Drops unsupported query parameters (asyncpg rejects unknown ones like channel_binding).
    """
    if not url:
        return url
    unsupported = {"channel_binding", "connect_timeout"}
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if "sslmode=" in url:
        url = url.replace("sslmode=", "ssl=")
    parsed = urlsplit(url)
    if parsed.query:
        filtered = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in unsupported]
        )
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, filtered, parsed.fragment))
    return url


# ── Engine & Session Factory ──────────────────────
engine = create_async_engine(
    normalize_database_url(settings.DATABASE_URL),
    echo=settings.APP_ENV == "development",
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
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
