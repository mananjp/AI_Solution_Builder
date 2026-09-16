"""
AI Solution Builder — FastAPI Application

Main entry point: middleware stack (request ID, logging, rate limiting,
audit, metrics), exception handler envelope, route registration, health
checks, and lifespan events (DB + Redis).
"""

import logging
from contextlib import asynccontextmanager

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
from app.api.solutions import router as solutions_router
from app.api.system import router as system_router
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
    async with engine.begin() as conn:
        # Import all models so they register with Base.metadata
        import app.models  # noqa: F401

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created/verified")
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


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "metrics": "/metrics",
    }
