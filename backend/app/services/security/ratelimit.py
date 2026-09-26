"""
AI Solution Builder — VirusTotal Rate Limiter
(Phase 5 of Threat Scanning Implementation Plan SEC-SCAN-001)

Redis-backed token bucket enforcing VirusTotal RPM and daily limits.
Fails open on Redis errors to prevent halting operations.
"""

from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def acquire_virustotal_quota() -> bool:
    """Attempt to acquire 1 request from VirusTotal token bucket.

    Returns True if quota is available, False if throttled.
    Shared across API processes and worker containers via Redis.
    """
    client = redis_client()
    if client is None:
        # Fail-open if Redis is not configured or down
        return True

    now = int(time.time())
    minute_bucket = now // 60
    day_bucket = now // 86400

    key_rpm = f"vt:ratelimit:rpm:{minute_bucket}"
    key_daily = f"vt:ratelimit:daily:{day_bucket}"

    try:
        pipeline = client.pipeline(transaction=True)
        pipeline.incr(key_rpm)
        pipeline.expire(key_rpm, 120)
        pipeline.incr(key_daily)
        pipeline.expire(key_daily, 172800)
        results = await pipeline.execute()

        rpm_count = int(results[0])
        daily_count = int(results[2])

        if rpm_count > settings.VIRUSTOTAL_RPM:
            logger.warning(
                "VirusTotal RPM limit reached (%d/%d for minute bucket %d)",
                rpm_count,
                settings.VIRUSTOTAL_RPM,
                minute_bucket,
            )
            return False

        if daily_count > settings.VIRUSTOTAL_DAILY:
            logger.warning(
                "VirusTotal daily quota reached (%d/%d for day bucket %d)",
                daily_count,
                settings.VIRUSTOTAL_DAILY,
                day_bucket,
            )
            return False

        return True
    except Exception as exc:
        logger.debug("Redis error checking VirusTotal rate limit, failing open: %s", exc)
        return True
