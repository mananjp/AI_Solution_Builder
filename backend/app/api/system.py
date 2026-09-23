"""
AI Solution Builder — System Endpoints

Liveness (/health), readiness (/ready), and Prometheus metrics (/metrics).
Ready checks both Postgres and Redis each time it is called.
"""

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text
from starlette.responses import Response

from app.core.config import settings
from app.core.database import engine
from app.core.metrics import metrics_response, set_db_health, set_redis_health
from app.core.redis import ping_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe — the process is running."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "env": settings.APP_ENV,
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness probe — verifies database and Redis connectivity."""
    db_up = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            # Guard against the P0 failure mode where the `plans` table is missing
            # (e.g. migrations that were never applied): surface it as not-ready.
            await conn.execute(text("SELECT 1 FROM plans LIMIT 1"))
    except Exception:
        logger.exception("DB readiness check failed")
        db_up = False

    redis_up = await ping_redis()
    set_db_health(db_up)
    set_redis_health(redis_up)

    checks = {"database": "up" if db_up else "down", "redis": "up" if redis_up else "down"}
    status_code = 200 if (db_up and redis_up) else 503
    return {
        "status": "ready" if status_code == 200 else "degraded",
        "checks": checks,
        "healthy": db_up and redis_up,
    }


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics in OpenMetrics text format."""
    return metrics_response()
