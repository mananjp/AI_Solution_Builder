"""
AI Solution Builder — Live system resource sampling.

Returns real CPU %, memory, and disk usage numbers for the runtime host so the
dashboard / build cards can show live observability instead of static badges.

psutil is optional: without it (constrained environments) CPU/memory come back
as null and disk usage falls back to the stdlib ``shutil.disk_usage``.
"""

import logging
import os
import shutil
import time
from typing import Any

logger = logging.getLogger(__name__)


async def system_resources() -> dict[str, Any]:
    """Sample host CPU, memory, and disk usage (never raises)."""
    cpu_percent: float | None = None
    cpu_count = os.cpu_count() or 0
    memory: dict[str, Any] | None = None
    try:
        import psutil  # optional dependency

        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        memory = {
            "used_mb": round(mem.used / 1048576, 1),
            "total_mb": round(mem.total / 1048576, 1),
            "percent": mem.percent,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("psutil unavailable (%s); CPU/memory sampling skipped", exc)

    disk_total: int | None = None
    disk_free: int | None = None
    disk_percent: float | None = None
    try:
        usage = shutil.disk_usage(".")
        disk_total = int(usage.total)
        disk_free = int(usage.free)
        if usage.total:
            disk_percent = round((1 - usage.free / usage.total) * 100, 1)
    except Exception as exc:  # noqa: BLE001
        logger.debug("disk_usage sampling failed: %s", exc)

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "memory": memory,
        "disk_total_bytes": disk_total,
        "disk_free_bytes": disk_free,
        "disk_percent": disk_percent,
        "sample_ts": round(time.time(), 3),
        "psutil_available": cpu_percent is not None,
    }