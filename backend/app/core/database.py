"""
AI Solution Builder — Async Database Engine

Async SQLAlchemy 2.0 with asyncpg driver for PostgreSQL.
Provides session factory and dependency injection for FastAPI routes.
"""

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── SQLite compatibility: render PostgreSQL-specific types on SQLite ──
# Models use `from sqlalchemy.dialects.postgresql import JSONB, UUID` which
# has no native SQLite DDL. Without this, `Base.metadata.create_all()` fails
# on `sqlite+aiosqlite` with "can't render element of type JSONB".
try:
    from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
    from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(_PG_JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
        return "JSON"

    @compiles(_PG_UUID, "sqlite")
    def _compile_uuid_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
        return "CHAR(36)"

    # SQLite stores UUIDs as plain 32-char hex strings, but the PostgreSQL
    # UUID bind processor calls `.hex` on every non-NULL value. That breaks
    # lookups that pass a string id (e.g. the JWT `sub` claim → `User.id == sub`),
    # raising `'str' object has no attribute 'hex'`. Normalize strings to hex
    # first so they bind identically to stored values.
    _orig_uuid_bind = _PG_UUID.bind_processor

    def _sqlite_uuid_bind_processor(self: Any, dialect: Any) -> Any:
        process = _orig_uuid_bind(self, dialect)  # type: ignore[no-untyped-call]
        if process is None or dialect.name != "sqlite":
            return process

        def wrapped(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, str):
                try:
                    return uuid.UUID(value).hex
                except (ValueError, AttributeError, TypeError):
                    return value
            return process(value)

        return wrapped

    _PG_UUID.bind_processor = _sqlite_uuid_bind_processor  # type: ignore[method-assign]
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
# asyncpg binds every connection to the event loop that opened it. Terminating one
# from a different, already-closed loop makes asyncpg call ``loop.create_task`` and
# raise ``RuntimeError: Event loop is closed``, which SQLAlchemy's pool reports as
# ``Exception terminating connection <asyncpg...>`` at ERROR level. The owning loop
# is recorded below so that teardown always happens where it was established.
_engine_loop: asyncio.AbstractEventLoop | None = None


def _engine_pool_kwargs() -> dict[str, Any]:
    """Pool configuration for the shared engine."""
    if settings.DB_POOL_DISABLE:
        # NullPool: connections are closed on release instead of being parked in the
        # pool, so nothing survives the request (or the event loop) that opened it.
        return {"poolclass": NullPool}
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }


def _build_engine() -> AsyncEngine:
    """Create the shared async engine and tag it with the loop that owns its pool."""
    new_engine = create_async_engine(
        normalize_database_url(settings.DATABASE_URL),
        echo=settings.APP_ENV == "development",
        pool_pre_ping=True,
        **_engine_pool_kwargs(),
    )

    @sa_event.listens_for(new_engine.sync_engine, "connect")
    def _record_owner_loop(dbapi_connection: Any, connection_record: Any) -> None:
        global _engine_loop
        with contextlib.suppress(RuntimeError):  # connect() with no running loop
            _engine_loop = asyncio.get_running_loop()

    return new_engine


engine = _build_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def dispose_engine() -> None:
    """Dispose the shared async engine from the event loop that owns its pool.

    Call this from the same loop the application serves requests on. If it is
    called from a different loop the parked connections belong to a loop that has
    stopped, so the pool is de-referenced without closing them — terminating them
    here is what makes asyncpg raise ``RuntimeError: Event loop is closed``.
    """
    global _engine_loop

    owner = _engine_loop
    _engine_loop = None

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover - dispose() from a sync context
        running = None

    if owner is None or running is owner:
        await engine.dispose()
        return

    logger.warning(
        "dispose_engine() called from a different event loop than the one that owns "
        "the connection pool (owner loop closed=%s, current loop=%s); dropping the "
        "stale pool without closing its connections",
        owner.is_closed(),
        "none" if running is None else f"id={id(running)}",
    )
    await engine.dispose(close=False)


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
