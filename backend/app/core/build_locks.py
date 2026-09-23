"""Serialized, race-safe MVP build-number allocation.

``SELECT MAX(build_number) + 1`` is not safe under concurrency: two simultaneous
builds for the same solution can observe the same max and both insert the same
``build_number``, corrupting workspace paths, "newest first" ordering, and
storage keys.

The MVP path targets a single uvicorn worker (``WORKER_MODE=inline``), so an
in-process per-solution asyncio lock fully closes the race window across
allocate -> insert -> flush -> commit. When the service is scaled to multiple
workers, replace this with a UNIQUE(solution_id, build_number) constraint plus
an IntegrityError retry loop.
"""

import asyncio
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mvp_build import MVPBuild

_solution_locks: dict[UUID, asyncio.Lock] = {}


async def _next_build_number(db: AsyncSession, solution_id: UUID) -> int:
    result = await db.execute(
        select(MVPBuild.build_number)
        .where(MVPBuild.solution_id == solution_id)
        .order_by(desc(MVPBuild.build_number))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1


async def allocate_build_number(db: AsyncSession, solution_id: UUID) -> tuple[asyncio.Lock, int]:
    """Acquire the per-solution lock and return ``(lock, next_build_number)``.

    Callers MUST hold the returned lock until their ``commit()`` completes —
    the number is only visible to other sessions once committed, so releasing
    early would let a concurrent build reuse it. Always release the lock in a
    ``finally`` block.
    """
    lock = _solution_locks.setdefault(solution_id, asyncio.Lock())
    await lock.acquire()
    try:
        return lock, await _next_build_number(db, solution_id)
    except BaseException:
        lock.release()
        raise