"""
AI Solution Builder — Live system resource sampling.

Returns real CPU %, memory, and disk usage numbers for the runtime host so the
dashboard / build cards can show live observability instead of static badges.

psutil is optional: without it (constrained environments) CPU/memory come back
as null and disk usage falls back to the stdlib ``shutil.disk_usage``.
"""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _read_number(path: str) -> int | None:
    try:
        value = Path(path).read_text(encoding="ascii").strip()
        return None if value == "max" else int(value)
    except (OSError, ValueError):
        return None


def _container_memory() -> tuple[int, int] | None:
    """Return cgroup memory used/limit in bytes when the container exposes it."""
    pairs = (
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"),
        (
            "/sys/fs/cgroup/memory/memory.usage_in_bytes",
            "/sys/fs/cgroup/memory/memory.limit_in_bytes",
        ),
    )
    for used_path, limit_path in pairs:
        used, limit = _read_number(used_path), _read_number(limit_path)
        # Some cgroup v1 hosts report a sentinel near 2**63 for "unlimited".
        if used is not None and limit is not None and 0 < limit < (1 << 60):
            return used, limit
    return None


def _container_cpu_quota() -> float | None:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="ascii").split()
        if quota != "max" and int(period) > 0:
            return max(0.01, int(quota) / int(period))
    except (OSError, ValueError):
        pass
    quota = _read_number("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period = _read_number("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if quota is not None and period and quota > 0:
        return max(0.01, quota / period)
    return None


def _container_cpu_usage_us() -> int | None:
    try:
        for line in Path("/sys/fs/cgroup/cpu.stat").read_text(encoding="ascii").splitlines():
            key, value = line.split(maxsplit=1)
            if key == "usage_usec":
                return int(value)
    except (OSError, ValueError):
        pass
    # cgroup v1 reports cpuacct usage as nanoseconds.
    usage_ns = _read_number("/sys/fs/cgroup/cpuacct/cpuacct.usage")
    if usage_ns is not None:
        return usage_ns // 1000
    return None


async def system_resources() -> dict[str, Any]:
    """Sample this container's CPU/memory limits and its build-volume disk."""
    cpu_percent: float | None = None
    cpu_count = _container_cpu_quota() or float(os.cpu_count() or 0)
    memory: dict[str, Any] | None = None

    cpu_before = _container_cpu_usage_us()
    if cpu_before is not None:
        await asyncio.sleep(0.1)
        cpu_after = _container_cpu_usage_us()
        if cpu_after is not None and cpu_count > 0:
            cpu_percent = max(
                0.0,
                min(100.0, (cpu_after - cpu_before) / 1_000 / cpu_count),
            )

    container_mem = _container_memory()
    if container_mem:
        used, total = container_mem
        memory = {
            "used_mb": round(used / 1048576, 1),
            "total_mb": round(total / 1048576, 1),
            "percent": round(min(100.0, used / total * 100), 1),
        }

    try:
        import psutil  # optional dependency

        if cpu_percent is None:
            cpu_percent = min(100.0, await asyncio.to_thread(psutil.cpu_percent, interval=0.1))
        if memory is None:
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
        build_dir = os.getenv("MVP_BUILD_DIR", "/workspace")
        usage = shutil.disk_usage(build_dir if os.path.exists(build_dir) else ".")
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
