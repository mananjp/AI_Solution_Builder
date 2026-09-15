"""
AI Solution Builder — Core Middleware

  * RequestIDMiddleware        — injects/extracts X-Request-ID and attaches it
                                  to request.state for logging & tracing
  * LogMiddleware              — structured request logging with duration
  * RateLimitMiddleware        — Redis sliding-window limits per user/IP,
                                  with a stricter limit on AI/chat routes
  * AuditLogMiddleware         — records mutating requests in audit_logs
  * LanguageMiddleware         — content-language detection for the
                                  multilingual pipeline (Section 10)
"""

import logging
import time
import uuid

from fastapi import Request
from sqlalchemy import text as sa_text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.i18n import pick_best_language
from app.core.redis import sliding_window_count

logger = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_HEALTH_PATHS = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
_AI_PATHS = ("/api/v1/chat", "/api/v1/export")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request carries a unique X-Request-ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        request.state.start_time = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LogMiddleware(BaseHTTPMiddleware):
    """Structured per-request logging with request ID and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = getattr(request.state, "request_id", "-")
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request error id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def _client_ip(request: Request) -> str | None:
    """Real peer IP; X-Forwarded-For is only honored behind a trusted proxy."""
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _client_identifier(request: Request) -> str:
    """Use the authenticated user sub when present, else the client IP."""
    sub = getattr(request.state, "user_sub", None)
    if sub:
        return f"user:{sub}"
    ip = _client_ip(request) or "unknown"
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis sliding-window rate limiting (fail-open if Redis is down)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        ident = _client_identifier(request)
        is_ai = request.url.path.startswith(_AI_PATHS)
        limit = settings.RATE_LIMIT_AI_REQUESTS if is_ai else settings.RATE_LIMIT_REQUESTS
        window = (
            settings.RATE_LIMIT_AI_WINDOW_SECONDS if is_ai else settings.RATE_LIMIT_WINDOW_SECONDS
        )
        key = f"rl:{ident}:{'ai' if is_ai else 'api'}"
        allowed, current = await sliding_window_count(key, limit, window)
        if not allowed:
            response = Response(
                status_code=429,
                content='{"error":{"code":"RATE_LIMIT_EXCEEDED","message":"Rate limit exceeded. Please slow down.","details":[]}}',
                media_type="application/json",
            )
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-Request-ID"] = getattr(request.state, "request_id", "-")
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        return response


class LanguageMiddleware(BaseHTTPMiddleware):
    """Detect the caller's language and expose it on request.state.

    Reads X-Content-Language (explicit) then Accept-Language, storing the
    normalized code on ``request.state.language`` and echoing a
    ``X-Content-Language`` response header for the frontend i18n layer.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        language = pick_best_language(
            request.headers.get("Accept-Language", ""),
            request.headers.get("X-Content-Language", ""),
            "",
        )
        request.state.language = language
        response = await call_next(request)
        response.headers["X-Content-Language"] = language
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Persist an audit entry for every authenticated mutating request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.method not in _MUTATING_METHODS or request.url.path in _HEALTH_PATHS:
            return response
        if response.status_code >= 400:
            return response

        path = request.url.path
        # Only audit tenant API traffic, not middleware/admin health routes
        if not path.startswith("/api/v1"):
            return response

        user_id = getattr(request.state, "user_sub", None)
        if user_id is None:
            return response

        try:
            async with async_session_factory() as session:
                await session.execute(
                    sa_text(
                        "INSERT INTO audit_logs (id, user_id, org_id, action, resource, "
                        "request_id, method, path, ip_address, status_code, created_at) "
                        "VALUES (gen_random_uuid(), :uid, :org, :action, :resource, :reqid, :method, :path, :ip, :status, NOW())"
                    ),
                    {
                        "uid": user_id,
                        "org": getattr(request.state, "org_id", None),
                        "action": request.method,
                        "resource": path,
                        "reqid": getattr(request.state, "request_id", None),
                        "method": request.method,
                        "path": path,
                        "ip": _client_ip(request),
                        "status": response.status_code,
                    },
                )
                await session.commit()
        except Exception:
            logger.warning("Audit log write failed for %s %s", request.method, path)
        return response
