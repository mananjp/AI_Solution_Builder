"""Integration tests for the Build Worker, Durable Queue & Startup Reconciler."""

import uuid
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import delete, select

from app.models.build_job import BuildJob
from app.models.mvp_build import MVPBuild
from app.worker import claim_next_job, process_one_job, reconcile_orphaned_jobs


@pytest.mark.asyncio
async def test_claim_next_job_atomic(session_factory, workspace_solution):
    solution_id = uuid.UUID(workspace_solution["solution_id"])

    async with session_factory() as db:
        await db.execute(delete(BuildJob))
        build = MVPBuild(
            solution_id=solution_id,
            build_number=1,
            status="queued",
            workspace_path="/tmp/ws1",
        )
        db.add(build)
        await db.flush()

        job = BuildJob(build_id=build.id, status="queued")
        db.add(job)
        await db.commit()

        # Claim the job
        claimed = await claim_next_job(db, "test-worker-1")
        assert claimed is not None
        assert claimed.build_id == build.id
        assert claimed.status == "running"
        assert claimed.claimed_by == "test-worker-1"
        assert claimed.attempts == 1
        assert claimed.heartbeat_at is not None

        # Build status should now be 'building'
        await db.refresh(build)
        assert build.status == "building"

        # Claiming again when queue is empty should return None
        claimed_empty = await claim_next_job(db, "test-worker-1")
        assert claimed_empty is None


@pytest.mark.asyncio
async def test_reconcile_orphaned_jobs_requeues_under_max_attempts(session_factory, workspace_solution):
    solution_id = uuid.UUID(workspace_solution["solution_id"])

    async with session_factory() as db:
        build = MVPBuild(
            solution_id=solution_id,
            build_number=2,
            status="building",
            workspace_path="/tmp/ws2",
        )
        db.add(build)
        await db.flush()

        # Job was claimed by dead worker 5 minutes ago with attempt 1 of 2
        stale_time = datetime.now(UTC) - timedelta(seconds=300)
        job = BuildJob(
            build_id=build.id,
            status="running",
            attempts=1,
            max_attempts=2,
            claimed_by="dead-worker-pid-999",
            claimed_at=stale_time,
            heartbeat_at=stale_time,
        )
        db.add(job)
        await db.commit()

        # Run startup reconciliation
        reconciled = await reconcile_orphaned_jobs(db, "new-worker", stale_seconds=60)
        assert reconciled == 1

        await db.refresh(job)
        await db.refresh(build)

        # Job should be reset to queued for retry
        assert job.status == "queued"
        assert job.claimed_by is None
        assert build.status == "queued"


@pytest.mark.asyncio
async def test_reconcile_orphaned_jobs_marks_failed_after_max_attempts(session_factory, workspace_solution):
    solution_id = uuid.UUID(workspace_solution["solution_id"])

    async with session_factory() as db:
        build = MVPBuild(
            solution_id=solution_id,
            build_number=3,
            status="building",
            workspace_path="/tmp/ws3",
        )
        db.add(build)
        await db.flush()

        # Job already tried 2 of 2 attempts and died
        stale_time = datetime.now(UTC) - timedelta(seconds=300)
        job = BuildJob(
            build_id=build.id,
            status="running",
            attempts=2,
            max_attempts=2,
            claimed_by="dead-worker-pid-888",
            claimed_at=stale_time,
            heartbeat_at=stale_time,
        )
        db.add(job)
        await db.commit()

        # Run startup reconciliation
        reconciled = await reconcile_orphaned_jobs(db, "new-worker", stale_seconds=60)
        assert reconciled == 1

        await db.refresh(job)
        await db.refresh(build)

        # Job should be marked failed
        assert job.status == "failed"
        assert "abandoned" in job.error_message.lower()
        assert build.status == "failed"
        assert "abandoned" in build.error_message.lower()


@pytest.mark.asyncio
async def test_process_one_job_execution(session_factory, workspace_solution, monkeypatch):
    solution_id = uuid.UUID(workspace_solution["solution_id"])

    executed_builds = []

    async def fake_execute(b_id):
        executed_builds.append(b_id)
        async with session_factory() as db:
            b = await db.get(MVPBuild, b_id)
            if b:
                b.status = "complete"
            j_res = await db.execute(select(BuildJob).where(BuildJob.build_id == b_id))
            j = j_res.scalar_one_or_none()
            if j:
                j.status = "completed"
            await db.commit()

    monkeypatch.setattr("app.worker.execute_build_job", fake_execute)

    async with session_factory() as db:
        await db.execute(delete(BuildJob))
        build = MVPBuild(
            solution_id=solution_id,
            build_number=4,
            status="queued",
            workspace_path="/tmp/ws4",
        )
        db.add(build)
        await db.flush()

        job = BuildJob(build_id=build.id, status="queued")
        db.add(job)
        await db.commit()
        build_id = build.id

    did_work = await process_one_job("test-worker-exec")
    assert did_work is True
    assert executed_builds == [build_id]

    async with session_factory() as db:
        j = (await db.execute(select(BuildJob).where(BuildJob.build_id == build_id))).scalar_one()
        b = await db.get(MVPBuild, build_id)
        assert j.status == "completed"
        assert b.status == "complete"
