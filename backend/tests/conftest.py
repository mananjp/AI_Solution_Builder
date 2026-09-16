"""Shared fixtures for the backend integration test suite (real dev DB)."""

import os
import uuid

os.environ.setdefault("LLM_PROVIDER", "mock")
# Force local disk storage for tests so builds never upload to real Cloudinary.
os.environ["STORAGE_BACKEND"] = "local"
# Isolate sidecar auth header tests from any developer .env OPENCODE_SERVER_PASSWORD.
os.environ["OPENCODE_SERVER_PASSWORD"] = ""

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.core.config import settings
from app.core.database import Base, get_db, normalize_database_url
from app.core.database import engine as app_engine
from main import app


@pytest_asyncio.fixture()
async def db_engine():
    engine = create_async_engine(normalize_database_url(settings.DATABASE_URL), echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    # The engine introspection path uses the app's module-level engine; clear
    # its pool so no connection is reused across pytest event loops.
    await app_engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture()
async def client(db_engine, session_factory):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def register_user(client: httpx.AsyncClient) -> dict:
    """Register a fresh unique user+org and return auth/session context."""
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "Testpass123!",
            "org_name": f"Org-{uuid.uuid4().hex[:6]}",
        },
    )
    assert resp.status_code == 201, resp.text
    return {
        "email": email,
        "headers": {"Authorization": f"Bearer {resp.json()['access_token']}"},
    }


@pytest_asyncio.fixture()
async def auth_client(client):
    """Authenticated client + JWT headers for a fresh user."""
    ctx = await register_user(client)
    return {"client": client, "headers": ctx["headers"], "email": ctx["email"]}


@pytest_asyncio.fixture()
async def workspace_solution(auth_client):
    """Create a workspace + solution owned by the test user."""
    client = auth_client["client"]
    headers = auth_client["headers"]

    resp = await client.post("/api/v1/workspaces", json={"name": "Test WS"}, headers=headers)
    assert resp.status_code == 201, resp.text
    workspace_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/solutions",
        json={"workspace_id": workspace_id, "title": "Test Solution"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    solution_id = resp.json()["id"]

    return {
        "client": client,
        "headers": headers,
        "workspace_id": workspace_id,
        "solution_id": solution_id,
    }
