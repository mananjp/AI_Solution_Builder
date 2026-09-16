"""
AI Solution Builder — Background Build Worker Process

Independent long-running worker process that polls and claims queued MVP builds
from the build_jobs table and executes them.

Key features:
1. Startup reconciliation: orphaned builds stuck in 'running'/'building' from
   previous crashed/redeployed workers are automatically requeued (or marked failed).
2. Atomic job claiming via PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED.
3. Periodic heartbeat updating heartbeat_at while the build runs.
4. Graceful shutdown on SIGTERM / SIGINT.
"""

import asyncio
import contextlib
import logging
import os
import signal
import socket
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mvp import execute_build_job
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.redis import close_redis, init_redis
from app.models.build_job import BuildJob
from app.models.mvp_build import MVPBuild

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

_shutdown_event = asyncio.Event()


def generate_worker_id() -> str:
    host = socket.gethostname()[:16]
    pid = os.getpid()
    rand = uuid.uuid4().hex[:6]
    return f"worker-{host}-{pid}-{rand}"


async def reconcile_orphaned_jobs(db: AsyncSession, worker_id: str, stale_seconds: int = 60) -> int:
    """Reconcile orphaned builds stuck in 'running' status.

    On worker startup, any job that was claimed but never completed is reconciled:
    - If attempts < max_attempts: reset status to 'queued' for retry.
    - If attempts >= max_attempts: mark as 'failed'.
    """
    threshold = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    result = await db.execute(
        select(BuildJob).where(
            BuildJob.status == "running",
            (BuildJob.heartbeat_at.is_(None)) | (BuildJob.heartbeat_at < threshold),
        )
    )
    orphans = result.scalars().all()
    if not orphans:
        logger.info("Startup reconciliation: no orphaned build jobs found.")
        return 0

    logger.warning("Startup reconciliation: found %d orphaned build job(s)", len(orphans))
    count = 0
    for job in orphans:
        build = await db.get(MVPBuild, job.build_id)
        if job.attempts < job.max_attempts:
            logger.warning(
                "Requeuing orphaned build %s (attempt %d/%d, was claimed by %s)",
                job.build_id,
                job.attempts,
                job.max_attempts,
                job.claimed_by,
            )
            job.status = "queued"
            job.claimed_by = None
            job.claimed_at = None
            if build and build.status == "building":
                build.status = "queued"
        else:
            logger.error(
                "Marking abandoned build %s as failed (exceeded %d attempts)",
                job.build_id,
                job.max_attempts,
            )
            job.status = "failed"
            job.error_message = "Build abandoned mid-execution (worker terminated or redeployed)"
            if build and build.status in ("building", "queued"):
                build.status = "failed"
                build.error_message = job.error_message
        count += 1

    await db.commit()
    logger.info("Reconciled %d orphaned build job(s)", count)
    return count


async def claim_next_job(db: AsyncSession, worker_id: str) -> BuildJob | None:
    """Atomically claim the oldest queued job using FOR UPDATE SKIP LOCKED."""
    dialect_name = db.bind.dialect.name if db.bind else ""
    query = (
        select(BuildJob)
        .where(BuildJob.status == "queued")
        .order_by(BuildJob.created_at.asc())
        .limit(1)
    )

    if dialect_name == "postgresql":
        query = query.with_for_update(of=BuildJob, skip_locked=True)
    else:
        # Fallback for SQLite in test environments
        query = query.with_for_update()

    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        return None

    now = datetime.now(UTC)
    job.status = "running"
    job.claimed_by = worker_id
    job.claimed_at = now
    job.heartbeat_at = now
    job.attempts += 1

    # Transition MVPBuild to building
    build = await db.get(MVPBuild, job.build_id)
    if build:
        build.status = "building"

    await db.commit()
    await db.refresh(job)
    logger.info(
        "Claimed build job %s (build_id=%s, attempt=%d) by %s",
        job.id,
        job.build_id,
        job.attempts,
        worker_id,
    )
    return job


async def _heartbeat_loop(
    build_id: uuid.UUID,
    stop_event: asyncio.Event,
    interval: float = 10.0,
) -> None:
    """Periodically update heartbeat_at for the active build job."""
    while not stop_event.is_set():
        try:
            await asyncio.sleep(interval)
            if stop_event.is_set():
                break
            async with async_session_factory() as db:
                result = await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))
                job = result.scalar_one_or_none()
                if job and job.status == "running":
                    job.heartbeat_at = datetime.now(UTC)
                    await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.debug("Heartbeat update failed: %s", exc)


async def process_one_job(worker_id: str) -> bool:
    """Claim and execute a single queued build job. Returns True if a job was processed."""
    async with async_session_factory() as db:
        job = await claim_next_job(db, worker_id)
        if not job:
            return False
        build_id = job.build_id

    # Start background heartbeat for this job
    stop_heartbeat = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(build_id, stop_heartbeat),
        name=f"heartbeat-{build_id}",
    )

    try:
        logger.info("Executing build job for build_id=%s...", build_id)
        await execute_build_job(build_id)
        logger.info("Finished build job for build_id=%s", build_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error executing build job %s: %s", build_id, exc)
    finally:
        stop_heartbeat.set()
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task

    return True


async def run_worker(worker_id: str | None = None) -> None:
    """Main worker loop."""
    wid = worker_id or generate_worker_id()
    logger.info("Build worker starting with ID: %s", wid)

    await init_redis()

    # 1. Startup reconciliation
    try:
        async with async_session_factory() as db:
            await reconcile_orphaned_jobs(db, wid)
    except Exception as exc:
        logger.error("Startup reconciliation failed: %s", exc)

    logger.info("Worker %s ready. Polling for queued builds...", wid)

    # 2. Main polling loop
    poll_interval = getattr(settings, "WORKER_POLL_INTERVAL", 2.0)
    while not _shutdown_event.is_set():
        try:
            did_work = await process_one_job(wid)
            if not did_work:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(_shutdown_event.wait(), timeout=poll_interval)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error in worker loop: %s", exc)
            await asyncio.sleep(poll_interval)

    logger.info("Worker %s shutting down...", wid)
    await close_redis()
    logger.info("Worker %s stopped cleanly.", wid)


def handle_signal() -> None:
    logger.info("Received termination signal — initiating graceful worker shutdown...")
    _shutdown_event.set()


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Attach signal handlers if supported (Windows has limited signal support)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, AttributeError):
            # Fallback for Windows
            signal.signal(sig, lambda *_: handle_signal())

    try:
        loop.run_until_complete(run_worker())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
