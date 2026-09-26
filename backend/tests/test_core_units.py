"""Unit tests for core services: async Redis, credit metering, document
parser, and JWT/password security."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis import asyncio as aioredis
from sqlalchemy import select

from app.core.credits import (
    action_cost,
    check_credits,
    credit_usage,
    require_and_deduct_credit,
)
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.ingestion.parser import (
    extract_readable_html,
    parse_csv_excel,
    parse_document,
    parse_openapi,
    parse_pdf,
    parse_text,
    parse_url,
)
from app.models.organization import Organization
from app.models.user import User


# ── Async Redis ─────────────────────────────────────
def _redis_reachable() -> bool:
    async def probe():
        client = aioredis.from_url(
            "redis://localhost:6379/0",
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
        )
        try:
            return bool(await client.ping())
        except Exception:
            return False
        finally:
            await client.aclose()

    try:
        return asyncio.run(probe())
    except Exception:
        return False


REDIS_OK = _redis_reachable()
redis_required = pytest.mark.skipif(not REDIS_OK, reason="Redis not reachable")


@redis_required
async def test_redis_lifecycle_and_ping():
    from app.core.redis import close_redis, init_redis, ping_redis, redis_client

    await close_redis()
    assert redis_client() is None
    assert await ping_redis() is False  # degraded mode before init

    await init_redis()
    assert redis_client() is not None
    assert await ping_redis() is True
    await close_redis()


@redis_required
async def test_redis_sliding_window_enforces_limit():
    from app.core.redis import init_redis, sliding_window_count

    await init_redis()
    key = "test-ratelimit-" + uuid4().hex
    results = [await sliding_window_count(key, 3, 60) for _ in range(4)]
    assert all(ok for ok, _ in results[:3])
    assert results[0][1] == 1
    allow, count = results[3]
    assert allow is False
    assert count == 4
    await sliding_window_count(key, 3, 60)  # keeps working
    from app.core.redis import close_redis

    await close_redis()


@redis_required
async def test_redis_json_cache_roundtrip():
    from app.core.redis import (
        close_redis,
        init_redis,
        redis_del,
        redis_get_json,
        redis_set_json,
    )

    await init_redis()
    key = "test-cache-" + uuid4().hex
    assert await redis_set_json(key, {"a": 1, "b": [2]}, ttl_seconds=30) is True
    assert await redis_get_json(key) == {"a": 1, "b": [2]}
    assert await redis_get_json("does-not-exist") is None
    await redis_del(key)
    assert await redis_get_json(key) is None
    await close_redis()


async def test_redis_functions_fail_open_when_client_none():
    from app.core.redis import (
        close_redis,
        ping_redis,
        redis_del,
        redis_get_json,
        redis_set_json,
        sliding_window_count,
    )

    await close_redis()
    assert await ping_redis() is False
    assert await sliding_window_count("kw", 5, 60) == (True, 0)
    assert await redis_set_json("k", {"x": 1}) is False
    assert await redis_get_json("k") is None
    await redis_del("k")  # no-op, must not raise


# ── Credit metering ─────────────────────────────────
def test_action_cost_known_and_unknown():
    assert action_cost("generation") > 0
    assert action_cost("export") == 2
    assert action_cost("no_such_action") == action_cost("generation")


async def test_check_credits_returns_org_balance(auth_client, session_factory):
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        assert await check_credits(db, user.org_id) == 200
        with pytest.raises(HTTPException) as exc:
            await check_credits(db, uuid4())
        assert exc.value.status_code == 404


async def test_require_and_deduct_credit(auth_client, session_factory):
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        org = (
            await db.execute(select(Organization).where(Organization.id == user.org_id))
        ).scalar_one()

        result = await require_and_deduct_credit(db, user, "generation", "Test deduction")
        assert result["cost"] == action_cost("generation")
        assert org.credits_remaining == 200 - result["cost"]

        # 'regenerate' aliases to regeneration metering
        regen = await require_and_deduct_credit(db, user, "regenerate", "Regen")
        assert regen["cost"] == action_cost("regeneration")


async def test_require_and_deduct_credit_402(auth_client, session_factory):
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        org = (
            await db.execute(select(Organization).where(Organization.id == user.org_id))
        ).scalar_one()
        org.credits_remaining = 1
        await db.flush()
        with pytest.raises(HTTPException) as exc:
            await require_and_deduct_credit(db, user, "generation")
        assert exc.value.status_code == 402
        assert exc.value.detail["code"] == "INSUFFICIENT_CREDITS"


async def test_require_and_deduct_credit_org_missing(auth_client, session_factory):
    from types import SimpleNamespace

    async with session_factory() as db:
        with pytest.raises(HTTPException) as exc:
            await require_and_deduct_credit(db, SimpleNamespace(org_id=uuid4()), "generation")
        assert exc.value.status_code == 404


async def test_require_and_deduct_credit_free_when_zero_cost(
    auth_client, session_factory, monkeypatch
):
    imported = __import__("app.core.credits", fromlist=["action_cost"])
    monkeypatch.setattr(imported, "action_cost", lambda action: 0)
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        out = await require_and_deduct_credit(db, user, "generation")
        assert out == {"credits_remaining": None, "deducted": 0, "cost": 0}


async def test_unlimited_org_skips_metering(auth_client, session_factory):
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        org = (
            await db.execute(select(Organization).where(Organization.id == user.org_id))
        ).scalar_one()
        org.credits_remaining = None
        await db.flush()

        assert await check_credits(db, user.org_id) is None
        result = await require_and_deduct_credit(db, user, "generation", "Unlimited gen")
        assert result == {
            "credits_remaining": None,
            "deducted": 0,
            "cost": action_cost("generation"),
        }
        assert org.credits_remaining is None


async def test_usage_reports_unlimited(auth_client, session_factory):
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        org = (
            await db.execute(select(Organization).where(Organization.id == user.org_id))
        ).scalar_one()
        org.credits_remaining = None
        await db.flush()
        usage = await credit_usage(db, user.org_id)
        assert usage["balance"] is None
        assert usage["total_spent"] == 0


async def test_credit_usage_aggregates(auth_client, session_factory):
    from app.core.credits import require_and_deduct_credit

    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        await require_and_deduct_credit(db, user, "generation", "Setup")
        usage = await credit_usage(db, user.org_id)
        assert usage["balance"] == 200 - action_cost("generation")
        assert usage["total_spent"] == action_cost("generation")
        assert usage["by_action"]["generation"] == action_cost("generation")
        assert usage["recent_transactions"][0]["action_type"] == "generation"


# ── Document parser ─────────────────────────────────
async def test_parse_text_utf8_and_fallback():
    assert await parse_text("héllo".encode()) == "héllo"
    assert await parse_text(b"\xff\xfe invalid utf8") == "\xff\xfe invalid utf8"


async def test_parse_document_routes_by_extension():
    assert await parse_document(b"plain", "notes.txt") == "plain"
    assert "PDF parsing error" in await parse_document(b"%PDF-1.4 broken", "file.pdf")
    assert "DOCX parsing error" in await parse_document(b"not a docx", "file.docx")
    assert "CSV/Excel parsing error" in await parse_document(b"not excel", "file.xlsx")
    # Unknown extension falls back to text parsing
    assert await parse_document(b"anything", "file.foo") == "anything"


async def test_parse_pdf_missing_input_errors_gracefully():
    out = await parse_pdf(b"\x00junk")
    assert "PDF parsing error" in out


async def test_parse_csv_excel_ok():
    csv_bytes = b"email,name\nq@example.com,Quinn\nz@example.com,Zed\n"
    out = await parse_csv_excel(csv_bytes, "catalog.csv")
    assert "Columns (2): email, name" in out
    assert "First 5 rows" in out


async def test_parse_document_json_yaml_text():
    assert await parse_document(b'{"a": 1}', "data.json") == '{"a": 1}'
    assert await parse_document(b"# Title", "notes.md") == "# Title"


def test_extract_readable_html_strips_markup():
    html = (
        "<html><head><title>t</title></head><body>"
        "<nav>Skip me</nav><script>var a = 1;</script><style>.c{}</style>"
        "<h1>Hello</h1><p>World</p></body></html>"
    )
    out = extract_readable_html(html)
    assert "Hello" in out
    assert "World" in out
    assert "Skip me" not in out
    assert "var a" not in out
    assert ".c" not in out


async def test_parse_url_rejects_invalid_target():
    with pytest.raises(ValueError):
        await parse_url("not a url")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "ftp://example.com/file",
    ],
)
async def test_parse_url_ssrf_guard_blocks_private_and_unsafe(url):
    with pytest.raises(ValueError, match="non-public|http/https"):
        await parse_url(url)


OPENAPI_JSON = b"""
{
  "openapi": "3.0.3",
  "info": {"title": "Pets API", "version": "1.0.0", "description": "Pet store"},
  "servers": [{"url": "https://api.example.com/v1"}],
  "tags": [{"name": "pets"}],
  "paths": {
    "/pets": {
      "get": {"summary": "List pets", "operationId": "listPets"},
      "post": {"summary": "Create pet"}
    }
  },
  "components": {
    "schemas": {
      "Pet": {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
    }
  }
}
"""


async def test_parse_openapi_json_summary():
    out = await parse_openapi(OPENAPI_JSON, "openapi.json")
    assert "OpenAPI Specification: Pets API (v1.0.0)" in out
    assert "GET /pets — List pets" in out
    assert "POST /pets — Create pet" in out
    assert "https://api.example.com/v1" in out
    assert "Tags: pets" in out
    assert "- Pet: id, name" in out


async def test_parse_openapi_yaml_summary():
    yaml_bytes = (
        b'swagger: "2.0"\n'
        b'info: {title: Legacy API, version: "0.9"}\n'
        b"basePath: /api\n"
        b"paths:\n"
        b"  /users:\n"
        b"    get: {summary: List users}\n"
        b"definitions:\n"
        b"  User:\n"
        b"    type: object\n"
        b"    properties:\n"
        b"      id: {type: integer}\n"
    )
    out = await parse_openapi(yaml_bytes, "spec.yaml")
    assert "Legacy API" in out
    assert "Base path: /api" in out
    assert "GET /users — List users" in out
    assert "- User: id" in out


async def test_parse_openapi_returns_none_for_plain_json():
    assert await parse_openapi(b'{"a": 1}', "data.json") is None


async def test_parse_document_routes_openapi_json():
    out = await parse_document(OPENAPI_JSON, "openapi.json")
    assert "OpenAPI Specification: Pets API" in out
    assert "GET /pets — List pets" in out


# ── Security ────────────────────────────────────────
def test_password_hashing_roundtrip():
    hashed = hash_password("S3cret!")
    assert verify_password("S3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_decode_token_expired_raises():
    token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-60))
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_token_invalid_signature_raises():
    with pytest.raises(HTTPException) as exc:
        decode_token("garbage.token.here")
    assert exc.value.status_code == 401


async def test_get_current_user_token_missing_subject(client):
    token = create_access_token({"other": "claim"})
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "subject" in resp.json()["error"]["message"]


async def test_get_current_user_token_unknown_user(client):
    token = create_access_token({"sub": str(uuid4())})
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "User not found"


async def test_get_current_user_deactivated(auth_client, session_factory):
    client = auth_client["client"]
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == auth_client["email"]))
        ).scalar_one()
        user.is_active = False
        await db.commit()
    resp = await client.get("/api/v1/auth/me", headers=auth_client["headers"])
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["error"]["message"]


def test_create_access_token_sets_expiry():
    import jwt as pyjwt

    from app.core.config import settings

    token = create_access_token({"sub": "abc"})
    payload = pyjwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "abc"
    assert "exp" in payload


def test_production_guard_rejects_placeholder_jwt_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    for secret in ("", "change-me", "change-this-to-a-long-random-string-in-production"):
        with pytest.raises(ValidationError):
            Settings(APP_ENV="production", JWT_SECRET_KEY=secret)


def test_production_guard_rejects_short_jwt_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", JWT_SECRET_KEY="simply-too-short")


def test_production_guard_accepts_strong_jwt_secret():
    from app.core.config import Settings

    s = Settings(APP_ENV="production", JWT_SECRET_KEY="a-strong-32+char-jwt-secret-6b4f0a9392")
    assert s.JWT_SECRET_KEY


def test_development_allows_placeholder_jwt_secret():
    from app.core.config import Settings

    s = Settings(APP_ENV="development", JWT_SECRET_KEY="change-me")
    assert s.JWT_SECRET_KEY == "change-me"


def test_secrets_encryption_roundtrip():
    from app.core.secrets import decrypt_secret, encrypt_secret

    plaintext = "ghp_super_secret_pat_token_12345"
    encrypted = encrypt_secret(plaintext)
    assert encrypted.startswith("enc:")
    assert encrypted != plaintext
    assert decrypt_secret(encrypted) == plaintext


def test_secrets_encryption_idempotent():
    from app.core.secrets import encrypt_secret

    plaintext = "ghp_token_abc"
    encrypted = encrypt_secret(plaintext)
    assert encrypt_secret(encrypted) == encrypted


def test_secrets_decrypt_legacy_plaintext():
    from app.core.secrets import decrypt_secret

    legacy_plaintext = "ghp_legacy_unencrypted_token"
    assert decrypt_secret(legacy_plaintext) == legacy_plaintext


def test_secrets_decrypt_invalid_token_returns_original():
    from app.core.secrets import decrypt_secret

    corrupted = "enc:not-a-valid-fernet-payload"
    assert decrypt_secret(corrupted) == corrupted


def test_status_code_name_unknown():
    from app.core.errors import _status_code_name

    assert _status_code_name(999) == "HTTP_ERROR"


async def test_unhandled_exception_handler():
    from unittest.mock import MagicMock

    from app.core.errors import unhandled_exception_handler

    req = MagicMock()
    req.method = "GET"
    req.url.path = "/test-unhandled"
    resp = await unhandled_exception_handler(req, RuntimeError("boom"))
    assert resp.status_code == 500


async def test_metrics_middleware_exception():
    from unittest.mock import AsyncMock, MagicMock

    from app.core.metrics import MetricsMiddleware

    app = MagicMock()
    middleware = MetricsMiddleware(app)
    req = MagicMock()
    req.url.path = "/api/v1/fail"
    req.method = "GET"
    call_next = AsyncMock(side_effect=RuntimeError("crash"))
    with pytest.raises(RuntimeError):
        await middleware.dispatch(req, call_next)


def test_normalize_database_url_neon():
    from app.core.database import normalize_database_url

    # Neon raw URL with postgresql:// and sslmode=require
    raw_neon = "postgresql://user:pass@ep-cool-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
    expected = (
        "postgresql+asyncpg://user:pass@ep-cool-123.us-east-2.aws.neon.tech/neondb?ssl=require"
    )
    assert normalize_database_url(raw_neon) == expected

    # postgres:// variant
    raw_postgres = "postgres://user:pass@ep-cool-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert normalize_database_url(raw_postgres) == expected

    # Already normalized
    assert normalize_database_url(expected) == expected

    # Empty
    assert normalize_database_url("") == ""


@pytest.mark.asyncio
async def test_ensure_default_plans_sync_runs_under_connection(db_engine) -> None:
    """Ensure plans seeding works via conn.run_sync, where run_sync hands the
    wrapper a Connection (no ORM add/flush). Regression for the AttributeError
    that broke the app lifespan on every startup."""
    from sqlalchemy import func, select

    from app.core.plans import DEFAULT_PLANS, ensure_default_plans_sync
    from app.models.credit import Plan

    async with db_engine.begin() as conn:
        await conn.run_sync(ensure_default_plans_sync)

    async with db_engine.begin() as conn:
        count = (
            await conn.execute(
                select(func.count())
                .select_from(Plan)
                .where(Plan.name.in_([p[0] for p in DEFAULT_PLANS]))  # type: ignore[type-var]
            )
        ).scalar_one()
    assert count == len(DEFAULT_PLANS)

    # Idempotent on a second run (rows already exist → no extra inserts).
    async with db_engine.begin() as conn:
        await conn.run_sync(ensure_default_plans_sync)
    async with db_engine.begin() as conn:
        count = (
            await conn.execute(
                select(func.count())
                .select_from(Plan)
                .where(Plan.name.in_([p[0] for p in DEFAULT_PLANS]))  # type: ignore[type-var]
            )
        ).scalar_one()
    assert count == len(DEFAULT_PLANS)
