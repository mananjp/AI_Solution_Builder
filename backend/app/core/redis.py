"""
AI Solution Builder — Async Redis Client

Lifespan-managed redis.asyncio client used for:
  * sliding-window rate limiting
  * embedding / industry-template caching
  * SSE coordination & export job queue
"""

import contextlib
import logging
import time
import uuid
from typing import Any

from redis import ResponseError
from redis import asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create the shared async Redis client on application startup."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        try:
            await _redis.ping()
            logger.info("Redis connection established")
        except Exception:
            logger.warning("Redis unavailable — degraded mode (rate limit/cache off)")


async def close_redis() -> None:
    """Close the shared Redis client on application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def redis_client() -> aioredis.Redis | None:
    """Return the shared client (may be None if Redis is down)."""
    return _redis


# Alias for compatibility across services
get_redis = redis_client


async def ping_redis() -> bool:
    """Health probe used by the /ready endpoint."""
    client = _redis
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception:
        return False


async def sliding_window_count(
    key: str,
    limit: int,
    window_seconds: int,
    client: aioredis.Redis | None = None,
) -> tuple[bool, int]:
    """Record one request against a sliding window.

    Returns (allowed, current_count). When Redis is unavailable the check is
    skipped (fail-open) so the API keeps working in degraded mode.
    """
    client = client or _redis
    if client is None:
        return True, 0
    try:
        now_ms = int(time.time() * 1000)
        pipeline = client.pipeline(transaction=True)
        pipeline.zremrangebyscore(key, "-inf", now_ms - window_seconds * 1000)
        pipeline.zadd(key, {f"{now_ms}-{uuid.uuid4().hex}": now_ms})
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds)
        _, _, count, _ = await pipeline.execute()
        return int(count) <= limit, int(count)
    except ResponseError:
        await client.execute_command("DEL", key)  # type: ignore[no-untyped-call]
        return True, 0
    except Exception:
        return True, 0


async def redis_set_json(key: str, value: dict[str, Any], ttl_seconds: int = 300) -> bool:
    """Cache a JSON-serializable dict in Redis."""
    import json

    client = _redis
    if client is None:
        return False
    try:
        return bool(await client.set(key, json.dumps(value), ex=ttl_seconds))
    except Exception:
        return False


async def redis_get_json(key: str) -> dict[str, Any] | None:
    """Fetch a cached JSON dict (None if missing or Redis down)."""
    import json

    client = _redis
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def redis_del(key: str) -> None:
    client = _redis
    if client is None:
        return
    with contextlib.suppress(Exception):
        await client.delete(key)
