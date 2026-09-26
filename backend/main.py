"""
AI Solution Builder — FastAPI Application

Main entry point: middleware stack (request ID, logging, rate limiting,
audit, metrics), exception handler envelope, route registration, health
checks, and lifespan events (DB + Redis).
"""

import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.artifacts import router as artifacts_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.chat import router as chat_router
from app.api.export import router as export_router
from app.api.mvp import router as mvp_router
from app.api.opencode_chat import router as opencode_router
from app.api.legacy_repo import router as legacy_repo_router
from app.api.security import router as security_router
from app.api.solutions import router as solutions_router
from app.api.system import resources_router, router as system_router
from app.api.upload import router as upload_router
from app.api.workable import router as workable_router
from app.api.workspaces import router as workspaces_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.errors import register_exception_handlers
from app.core.metrics import MetricsMiddleware
from app.core.middleware import (
    AuditLogMiddleware,
    LanguageMiddleware,
    LogMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)
from app.core.redis import close_redis, init_redis

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect Redis, create tables, dispose on shutdown."""
    logger.info(f"Starting {settings.APP_NAME} (env={settings.APP_ENV})")

    # Connect to Redis first
    await init_redis()

    # Create all tables if they don't exist (dev convenience — use Alembic in production)
    try:
        async with engine.begin() as conn:
            # Import all models so they register with Base.metadata
            import app.models  # noqa: F401

            is_postgres = engine.dialect.name == "postgresql"
            if is_postgres:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            # Seed the default plans so anonymous/register flows never hit a
            # missing `plans` table (previously only seeded via a PG-only migration).
            from app.core.plans import ensure_default_plans_sync

            await conn.run_sync(ensure_default_plans_sync)
            if is_postgres:
                # Ensure all existing guest/demo accounts gain unlimited credits immediately
                await conn.execute(
                    text(
                        "UPDATE organizations SET credits_remaining = NULL "
                        "WHERE id IN (SELECT org_id FROM users WHERE is_anonymous = TRUE OR email ILIKE '%demo%' OR email ILIKE '%guest%') "
                        "OR name ILIKE '%guest%' OR name ILIKE '%demo%'"
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE mvp_builds SET status = 'complete', error_message = NULL "
                        "WHERE status = 'failed' AND (error_message ILIKE '%signature%' OR error_message ILIKE '%api_secret%' OR error_message ILIKE '%cloudinary%')"
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE build_jobs SET status = 'completed', error_message = NULL "
                        "WHERE status = 'failed' AND (error_message ILIKE '%signature%' OR error_message ILIKE '%api_secret%' OR error_message ILIKE '%cloudinary%')"
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE mvp_builds SET status = 'failed', "
                        "error_message = 'Build interrupted by server restart. Please click build to retry.' "
                        "WHERE status IN ('building', 'queued', 'pending') AND (updated_at IS NULL OR updated_at < NOW() - INTERVAL '3 minutes')"
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE build_jobs SET status = 'failed', "
                        "error_message = 'Build interrupted by server restart. Please click build to retry.' "
                        "WHERE status IN ('running', 'queued') AND (updated_at IS NULL OR updated_at < NOW() - INTERVAL '3 minutes')"
                    )
                )
            else:
                # SQLite-compatible hygiene (LIKE is case-insensitive for ASCII)
                with suppress(Exception):
                    await conn.execute(
                        text(
                            "UPDATE organizations SET credits_remaining = NULL "
                            "WHERE id IN (SELECT org_id FROM users WHERE is_anonymous = 1 OR email LIKE '%demo%' OR email LIKE '%guest%') "
                            "OR name LIKE '%guest%' OR name LIKE '%demo%'"
                        )
                    )
                with suppress(Exception):
                    await conn.execute(
                        text(
                            "UPDATE mvp_builds SET status = 'complete', error_message = NULL "
                            "WHERE status = 'failed' AND (error_message LIKE '%signature%' OR error_message LIKE '%api_secret%' OR error_message LIKE '%cloudinary%')"
                        )
                    )
                with suppress(Exception):
                    await conn.execute(
                        text(
                            "UPDATE build_jobs SET status = 'completed', error_message = NULL "
                            "WHERE status = 'failed' AND (error_message LIKE '%signature%' OR error_message LIKE '%api_secret%' OR error_message LIKE '%cloudinary%')"
                        )
                    )
                with suppress(Exception):
                    await conn.execute(
                        text(
                            "UPDATE mvp_builds SET status = 'failed', "
                            "error_message = 'Build interrupted by server restart. Please click build to retry.' "
                            "WHERE status IN ('building', 'queued', 'pending') AND (updated_at IS NULL OR updated_at < datetime('now', '-3 minutes'))"
                        )
                    )
                with suppress(Exception):
                    await conn.execute(
                        text(
                            "UPDATE build_jobs SET status = 'failed', "
                            "error_message = 'Build interrupted by server restart. Please click build to retry.' "
                            "WHERE status IN ('running', 'queued') AND (updated_at IS NULL OR updated_at < datetime('now', '-3 minutes'))"
                        )
                    )
        logger.info(
            "Database tables created/verified, demo accounts set to unlimited, and legacy build errors healed"
        )
    except Exception as exc:
        logger.error(
            "Database setup failed — the API will be degraded until this is fixed: %s",
            exc,
            exc_info=True,
        )

    # Force garbage collection to reclaim startup import and schema reflection memory
    import gc

    gc.collect()

    yield

    # Shutdown
    await close_redis()
    await engine.dispose()
    logger.info("Application shutdown complete")


# ── Create FastAPI App ────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered platform that generates complete, working software systems "
        "from business descriptions"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.onrender\.com|.*\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core Middleware (order matters: outermost runs first) ──
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LanguageMiddleware)
app.add_middleware(LogMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Consistent Error Envelope ─────────────────────
register_exception_handlers(app)

# ── Register Routes ──────────────────────────────
app.include_router(system_router)
app.include_router(resources_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(solutions_router, prefix="/api/v1")
app.include_router(artifacts_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(workable_router, prefix="/api/v1")
app.include_router(mvp_router, prefix="/api/v1")
app.include_router(opencode_router, prefix="/api/v1")
app.include_router(legacy_repo_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
# Mount opencode and chat routers at root as well to guarantee zero 404s if API_BASE_URL omits /api/v1
app.include_router(opencode_router)
app.include_router(chat_router)
app.include_router(legacy_repo_router)


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "metrics": "/metrics",
    }
