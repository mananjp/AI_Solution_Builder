"""These are pure unit tests: no database, no network, no AI calls.

The top-level tests/conftest.py opens a Postgres+pgvector engine for every
session. Override it here with a no-op so this file can run anywhere, including
a laptop with nothing installed.
"""

import pytest_asyncio


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_engine():
    yield None
