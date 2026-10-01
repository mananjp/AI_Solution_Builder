"""Regression coverage for the engine / event-loop lifecycle contract.

Reproduces the reported failure —

    Exception terminating connection <asyncpg.connection.Connection ...>
    RuntimeError: Event loop is closed

asyncpg records the loop that opened a connection and calls ``loop.create_task``
on it to cancel an in-flight command. If SQLAlchemy's pool terminates that
connection after the owning loop closed, the call raises. The suite is structured
so the condition cannot arise (see ``conftest.py``); these tests pin that down.
"""

import asyncio
import logging

import pytest
from conftest import TEST_DATABASE_URL, _resolve_test_database_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.pool.impl import AsyncAdaptedQueuePool

from app.core import database
from app.core.config import settings

POOL_LOGGER = "sqlalchemy.pool"


def _pool_errors(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Pool teardown failures, i.e. what Sentry captured as the issue."""
    return [
        record
        for record in caplog.records
        if record.name.startswith(POOL_LOGGER) and record.levelno >= logging.ERROR
    ]


def _ownership_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "different event loop than the one that owns" in record.getMessage()
    ]


def _park_one_connection(engine: object) -> None:
    """Open then release a connection so the pool holds it, on a throwaway loop."""
    import concurrent.futures

    async def run() -> None:
        async with engine.connect():  # type: ignore[attr-defined]
            pass

    def thread_runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(thread_runner)
        future.result()


async def test_pooled_engine_disposes_cleanly_on_owning_loop(caplog):
    """Baseline: a pooled engine torn down on the loop that opened it is silent."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_size=1, max_overflow=0)
    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
    async with engine.connect():
        pass
    assert engine.pool.checkedin() == 1, "expected a parked connection"

    with caplog.at_level(logging.ERROR, logger=POOL_LOGGER):
        await engine.dispose()

    assert _pool_errors(caplog) == []


async def test_dispose_engine_warns_and_drops_pool_from_dead_owner_loop(monkeypatch, caplog):
    """The reported bug, end to end.

    A connection is parked on a loop that is then closed — exactly what happens
    when one process drives several loops. Terminating it from the live loop
    makes asyncpg call ``create_task`` on the closed loop. ``dispose_engine()``
    must de-reference that pool instead, and say so.
    """
    pooled = create_async_engine(TEST_DATABASE_URL, echo=False, pool_size=1, max_overflow=0)
    _park_one_connection(pooled)
    assert pooled.pool.checkedin() == 1

    owner = asyncio.new_event_loop()
    monkeypatch.setattr(database, "engine", pooled)
    monkeypatch.setattr(database, "_engine_loop", owner)
    owner.close()

    try:
        with caplog.at_level(logging.WARNING):
            await database.dispose_engine()
    finally:
        monkeypatch.undo()

    assert _pool_errors(caplog) == [], "pool teardown must not surface an unhandled ERROR"
    warnings = _ownership_warnings(caplog)
    assert len(warnings) == 1, f"expected one explanatory warning, got {warnings}"
    assert "owner loop closed=True" in warnings[0]
    assert database._engine_loop is None


async def test_dispose_engine_is_silent_on_the_owning_loop(caplog, monkeypatch):
    """The normal path (lifespan shutdown, worker exit) stays warning-free."""
    monkeypatch.setattr(database, "_engine_loop", asyncio.get_running_loop())
    with caplog.at_level(logging.WARNING, logger="app.core.database"):
        await database.dispose_engine()
    assert _ownership_warnings(caplog) == []
    assert database._engine_loop is None


def test_shared_app_engine_is_unpooled_in_tests():
    """The session loop is the only loop the suite runs on, so the shared engine
    must not park connections that some later loop would try to terminate."""
    assert settings.DB_POOL_DISABLE is True
    assert isinstance(database.engine.pool, NullPool)
    assert database.engine.pool.status() == "NullPool"


async def test_session_engine_is_shared_and_unpooled(db_engine):
    """``db_engine`` is session-scoped and disposed once, on the session loop."""
    assert isinstance(db_engine.pool, NullPool)
    assert db_engine.pool.status() == "NullPool"


def test_suite_targets_a_test_database():
    """The conftest guard must not be bypassed by the committed configuration."""
    assert "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0].lower()


@pytest.mark.parametrize(
    "url",
    ["postgresql://u:p@host/neondb", "postgresql+asyncpg://u:p@host/mydb?sslmode=require"],
)
def test_guard_rejects_non_test_databases(url, monkeypatch):
    """Only a database name containing 'test' is accepted, unless overridden."""
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    monkeypatch.delenv("ALLOW_NON_TEST_DB", raising=False)
    with pytest.raises(RuntimeError, match="Refusing to run tests"):
        _resolve_test_database_url()

    monkeypatch.setenv("ALLOW_NON_TEST_DB", "1")
    resolved = _resolve_test_database_url()
    db_name = resolved.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    expected_name = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    assert db_name == expected_name


def test_guard_accepts_test_database(monkeypatch):
    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/ci_test"
    )
    monkeypatch.delenv("ALLOW_NON_TEST_DB", raising=False)
    assert _resolve_test_database_url().endswith("ci_test")
