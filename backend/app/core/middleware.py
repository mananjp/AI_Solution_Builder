"""
AI Solution Builder — Core Middleware

  * RequestIDMiddleware        — injects/extracts X-Request-ID and attaches it
                                  to request.state for logging & tracing
  * LogMiddleware              — structured request logging with duration
  * RateLimitMiddleware        — sliding-window limits per user/IP,
                                  with a stricter limit on AI/chat routes
  * InputSanitizationMiddleware — validates and sanitizes request bodies
  * AuditLogMiddleware         — records mutating requests in audit_logs
  * LanguageMiddleware         — content-language detection for the
                                  multilingual pipeline (Section 10)
"""

import json
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
from app.core.sanitization import sanitize_input, MAX_MESSAGE_LENGTH

logger = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_HEALTH_PATHS = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
_AI_PATHS = ("/api/v1/chat", "/api/v1/export")


def _client_identifier(request: Request) -> str:
    """Use the authenticated user sub when present, else the client IP."""
    sub = getattr(request.state, "user_sub", None)
    if sub:
        return f"user:{sub}"
    forwarded = request.headers.get("X-Forwarded-For")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else request.client.host
        if request.client
        else "unknown"
    )
    return f"ip:{ip}"


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiting with automatic Redis/in-memory fallback."""

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

        # Try Redis first, fall back to in-memory
        allowed = True
        current = 0
        try:
            from app.core.redis import sliding_window_count
            allowed, current = await sliding_window_count(key, limit, window)
        except Exception:
            # Redis unavailable — use in-memory limiter
            from app.core.rate_limiter import rate_limiter
            info = rate_limiter.check(key, limit, window)
            if isinstance(info, tuple):
                allowed, info_dict = info
                current = limit - info_dict.get('remaining', limit)
            else:
                # Fallback: allow the request
                allowed = True

        if not allowed:
            response = Response(
                status_code=429,
                content=json.dumps({
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down.",
                        "retry_after_seconds": 60,
                    }
                }),
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


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Validate and sanitize request bodies on mutating AI endpoints.
    
    Checks for prompt injection, harmful content, and length violations
    before the request reaches any route handler.
    """

    _SANITIZE_PATHS = ("/api/v1/chat", "/api/v1/upload")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only sanitize mutating requests to specific paths
        if request.method not in _MUTATING_METHODS or request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        should_sanitize = any(request.url.path.startswith(p) for p in self._SANITIZE_PATHS)
        if not should_sanitize:
            return await call_next(request)

        # Read and validate body
        try:
            body = await request.body()
            if not body:
                return await call_next(request)

            data = json.loads(body)

            # Check text fields for injection
            text_fields = ["message", "content", "text", "prompt", "query", "url"]
            for field in text_fields:
                if field in data and isinstance(data[field], str):
                    result = sanitize_input(data[field])
                    if not result.is_safe:
                        logger.warning(
                            "Input rejected: field=%s reason=%s category=%s ip=%s",
                            field,
                            result.reason,
                            result.category,
                            _client_identifier(request),
                        )
                        return Response(
                            status_code=400,
                            content=json.dumps({
                                "error": {
                                    "code": "INPUT_REJECTED",
                                    "message": result.reason,
                                    "category": result.category,
                                }
                            }),
                            media_type="application/json",
                        )
                    # Replace with sanitized version
                    if result.sanitized_text:
                        data[field] = result.sanitized_text

            # Re-serialize and create new request
            sanitized_body = json.dumps(data).encode("utf-8")
            request._body = sanitized_body

        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not JSON or malformed — let the route handler deal with it
            pass
        except Exception:
            logger.warning("Sanitization middleware error", exc_info=True)

        return await call_next(request)


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
                        "ip": request.headers.get("X-Forwarded-For")
                        or (request.client.host if request.client else None),
                        "status": response.status_code,
                    },
                )
                await session.commit()
        except Exception:
            logger.warning("Audit log write failed for %s %s", request.method, path)
        return response
