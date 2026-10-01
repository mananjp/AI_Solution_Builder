"""Unit tests boosting test coverage across pure services and core utilities.

Covers razorpay_gateway, i18n, plans, figma, errors, metrics, and security types.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from httpx import MockTransport, Response

from app.core import errors, i18n, metrics, plans
from app.services import figma, razorpay_gateway
from app.services.security import types as sec_types

# ── Razorpay Gateway ──────────────────────────────────────────────────────────


def test_razorpay_configured():
    assert razorpay_gateway.razorpay_configured(key_id="rzp_123", key_secret="sec_456") is True
    assert razorpay_gateway.razorpay_configured(key_id="", key_secret="sec_456") is False
    assert razorpay_gateway.razorpay_configured(key_id="rzp_123", key_secret="") is False


def test_razorpay_auth_header():
    header = razorpay_gateway._auth_header("key", "secret")
    expected = "Basic " + base64.b64encode(b"key:secret").decode()
    assert header == {"Authorization": expected}


@pytest.mark.asyncio
async def test_razorpay_create_order_success(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        assert request.url.path == "/v1/orders"
        return Response(
            201,
            json={"id": "order_test_123", "amount": 50000, "currency": "INR", "status": "created"},
        )

    client = httpx.AsyncClient(transport=MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: client)

    res = await razorpay_gateway.create_order(
        key_id="k", key_secret="s", amount=50000, receipt="rcpt_1", notes={"item": "credits"}
    )
    assert res["id"] == "order_test_123"
    assert res["amount"] == 50000


@pytest.mark.asyncio
async def test_razorpay_create_order_failure(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(400, json={"error": {"description": "Invalid amount"}})

    client = httpx.AsyncClient(transport=MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: client)

    with pytest.raises(razorpay_gateway.RazorpayError, match="HTTP 400"):
        await razorpay_gateway.create_order(
            key_id="k", key_secret="s", amount=-10, receipt="rcpt_bad"
        )


@pytest.mark.asyncio
async def test_razorpay_create_order_missing_id(monkeypatch):
    async def handler(request: httpx.Request) -> Response:
        return Response(200, json={"status": "created"})

    client = httpx.AsyncClient(transport=MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: client)

    with pytest.raises(razorpay_gateway.RazorpayError, match="returned no order id"):
        await razorpay_gateway.create_order(
            key_id="k", key_secret="s", amount=100, receipt="rcpt_2"
        )


# ── i18n & Multilingual ───────────────────────────────────────────────────────


def test_i18n_rtl():
    assert i18n.is_rtl("ar") is True
    assert i18n.is_rtl("ur") is True
    assert i18n.is_rtl("fa") is True
    assert i18n.is_rtl("he") is True
    assert i18n.is_rtl("en") is False
    assert i18n.is_rtl("es") is False
    assert i18n.is_rtl("") is False


def test_i18n_normalize_language():
    assert i18n.normalize_language_code("guj") == "gu"
    assert i18n.normalize_language_code("HINDI") == "hi"
    assert i18n.normalize_language_code("en-US") == "en"
    assert i18n.normalize_language_code("zh-CN") == "zh"
    assert i18n.normalize_language_code("unknown_xyz", default="fr") == "fr"
    assert i18n.normalize_language_code("", default="") == ""


def test_i18n_detect_indic_script():
    assert i18n.detect_indic_script("નમસ્તે ગુજરાત") == "gu"
    assert i18n.detect_indic_script("नमस्ते भारत") == "hi"
    assert i18n.detect_indic_script("नमस्कर ळ") == "mr"
    assert i18n.detect_indic_script("आहे नाही करा माझे") == "mr"
    assert i18n.detect_indic_script("নমস্কার") == "bn"
    assert i18n.detect_indic_script("নমস্কাৰ \u09f0") == "as"
    assert i18n.detect_indic_script("ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ") == "pa"
    assert i18n.detect_indic_script("ନମସ୍କାର") == "or"
    assert i18n.detect_indic_script("வணக்கம்") == "ta"
    assert i18n.detect_indic_script("నమస్కారం") == "te"
    assert i18n.detect_indic_script("ನಮಸ್ಕಾರ") == "kn"
    assert i18n.detect_indic_script("നമസ്കാരം") == "ml"
    assert i18n.detect_indic_script("سلام دنیا") == "ur"
    assert i18n.detect_indic_script("Hello world") == ""
    assert i18n.detect_indic_script("") == ""


def test_i18n_detect_language_and_pick():
    assert i18n.detect_language("") == "en"
    assert i18n.detect_language("નમસ્તે ગુજરાત") == "gu"
    assert i18n.detect_language("Hello this is English text") == "en"

    # pick_best_language
    assert i18n.pick_best_language("", "gu", "hello") == "gu"
    assert i18n.pick_best_language("en-US", "", "નમસ્તે") == "gu"
    assert i18n.pick_best_language("fr", "", "hello") == "fr"
    assert i18n.pick_best_language("", "", "hello", default="es") in ("en", "es")


@pytest.mark.asyncio
async def test_i18n_translate_text_disabled(monkeypatch):
    monkeypatch.setattr(i18n.settings, "TRANSLATION_ENABLED", False)
    res = await i18n.translate_text("hello", "fr")
    assert res == "hello"

    monkeypatch.setattr(i18n.settings, "TRANSLATION_ENABLED", True)
    assert await i18n.translate_text("", "fr") == ""
    assert await i18n.translate_text("hello", "en") == "hello"


# ── Monetization Plans ────────────────────────────────────────────────────────


def test_plans_rows():
    rows = plans._plan_rows()
    assert len(rows) == 3
    names = {r["name"] for r in rows}
    assert {"free", "pro", "enterprise"} == names


@pytest.mark.asyncio
async def test_plans_ensure_default_plans():
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    await plans.ensure_default_plans(mock_db)
    assert mock_db.add.call_count == 3
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_plans_get_or_create_free_plan_exists():
    mock_db = MagicMock()
    mock_plan = MagicMock(name="PlanObject")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_plan
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await plans.get_or_create_free_plan(mock_db)
    assert result == mock_plan


# ── Figma Helper ─────────────────────────────────────────────────────────────


def test_figma_manifest_generation():
    bundle = {
        "title": "Test App Wireframes",
        "status": "complete",
        "wireframes": [
            {
                "name": "Dashboard Page",
                "screens": [
                    {
                        "name": "Overview",
                        "components": [
                            {"title": "Header Bar", "description": "Top navigation"},
                            {"type": "Button", "description": "Click me"},
                        ],
                    }
                ],
            }
        ],
    }

    manifest = figma.build_figma_manifest(bundle)
    assert manifest["name"] == "Test App Wireframes"
    assert manifest["type"] == "FILE"
    assert len(manifest["children"]) == 1
    page = manifest["children"][0]
    assert page["name"] == "Dashboard Page"
    assert len(page["children"]) == 1
    screen = page["children"][0]
    assert screen["name"] == "Overview"
    assert len(screen["children"]) == 2

    # Fallback with artifacts array
    art_bundle = {
        "artifacts": [
            {
                "artifact_type": "wireframe",
                "content": {
                    "module": "Auth Module",
                    "screens": [{"name": "Login", "components": []}],
                },
            }
        ]
    }
    art_manifest = figma.build_figma_manifest(art_bundle)
    assert len(art_manifest["children"]) == 1
    assert art_manifest["children"][0]["name"] == "Auth Module"


# ── Errors & Exception Handlers ───────────────────────────────────────────────


def test_errors_status_code_name():
    assert errors._status_code_name(422) == "UNPROCESSABLE_ENTITY"
    assert errors._status_code_name(404) == "NOT_FOUND"
    assert errors._status_code_name(999) == "HTTP_ERROR"


def test_error_response_builder():
    resp = errors.error_response(
        code="TEST_CODE",
        message="Test msg",
        details=[{"foo": "bar"}],
        http_code=400,
        headers={"X-Test": "1"},
    )
    assert resp.status_code == 400
    assert resp.headers["x-test"] == "1"


@pytest.mark.asyncio
async def test_http_exception_handler():
    req = MagicMock(spec=Request)
    # Simple string detail
    exc_simple = HTTPException(status_code=403, detail="Forbidden action")
    res1 = await errors.http_exception_handler(req, exc_simple)
    assert res1.status_code == 403

    # Dict detail
    exc_dict = HTTPException(
        status_code=400,
        detail={"code": "BAD_INPUT", "message": "Wrong input", "details": ["err1"]},
    )
    res2 = await errors.http_exception_handler(req, exc_dict)
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_validation_exception_handler():
    req = MagicMock(spec=Request)
    val_exc = RequestValidationError(
        errors=[
            {"loc": ["body", "email"], "msg": "value is not a valid email", "type": "value_error"}
        ]
    )
    res = await errors.validation_exception_handler(req, val_exc)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_unhandled_exception_handler():
    req = MagicMock(spec=Request)
    req.method = "GET"
    req.url.path = "/api/broken"
    res = await errors.unhandled_exception_handler(req, RuntimeError("boom"))
    assert res.status_code == 500


def test_register_exception_handlers():
    app = FastAPI()
    errors.register_exception_handlers(app)
    assert HTTPException in app.exception_handlers


# ── Metrics ───────────────────────────────────────────────────────────────────


def test_metrics_utilities():
    assert (
        metrics._metric_path("/solutions/12345678-1234-5678-1234-567812345678") == "/solutions/:id"
    )
    assert metrics._metric_path("/items/123") == "/items/:id"
    assert metrics._metric_path("/health") == "/health"

    metrics.set_db_health(True)
    metrics.set_db_health(False)
    metrics.set_redis_health(True)
    metrics.set_scanner_health("clamav", True)

    resp = metrics.metrics_response()
    assert resp.status_code == 200
    assert "http_requests_total" in resp.body.decode()


# ── Security Types ────────────────────────────────────────────────────────────


def test_security_worst_verdict():
    f_clean = sec_types.ScanFinding(
        source="clamav", verdict=sec_types.ScanVerdict.CLEAN, reason="clean"
    )
    f_suspicious = sec_types.ScanFinding(
        source="clamav", verdict=sec_types.ScanVerdict.SUSPICIOUS, reason="suspicious"
    )
    f_malicious = sec_types.ScanFinding(
        source="virustotal", verdict=sec_types.ScanVerdict.MALICIOUS, reason="virus"
    )
    f_error = sec_types.ScanFinding(
        source="clamav", verdict=sec_types.ScanVerdict.ERROR, reason="timeout"
    )

    assert sec_types.worst_verdict([]) == sec_types.ScanVerdict.CLEAN
    assert sec_types.worst_verdict([f_clean, f_suspicious]) == sec_types.ScanVerdict.SUSPICIOUS
    assert (
        sec_types.worst_verdict([f_clean, f_suspicious, f_malicious])
        == sec_types.ScanVerdict.MALICIOUS
    )
    assert sec_types.worst_verdict([f_error]) == sec_types.ScanVerdict.CLEAN


def test_security_exceptions():
    err1 = sec_types.ScanBlockedError("blocked", findings=[])
    assert str(err1) == "blocked"

    err2 = sec_types.ScanQuarantinedError("quarantine")
    assert str(err2) == "quarantine"

    err3 = sec_types.ScannerUnavailableError("unavailable")
    assert str(err3) == "unavailable"

    err4 = sec_types.ArchiveRejectedError("rejected")
    assert isinstance(err4, sec_types.ScanBlockedError)
