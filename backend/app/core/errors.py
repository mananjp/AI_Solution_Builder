"""
AI Solution Builder — Consistent Error Responses

Every API error is returned in a single envelope so clients can handle
failures uniformly:

    {"error": {"code": "...", "message": "...", "details": [...]}}
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _status_code_name(code: int) -> str:
    try:
        return HTTPStatus(code).phrase.upper().replace(" ", "_")
    except ValueError:
        return "HTTP_ERROR"


def error_response(
    code: str,
    message: str,
    details: list[Any] | None = None,
    http_code: int = status.HTTP_400_BAD_REQUEST,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a JSON error response in the standard envelope."""
    return JSONResponse(
        status_code=http_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            }
        },
        headers=dict(headers or {}),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return error_response(
        code=_status_code_name(exc.status_code)
        if not isinstance(exc.detail, dict)
        else str(exc.detail.get("code", _status_code_name(exc.status_code))),
        message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        details=exc.detail.get("details", []) if isinstance(exc.detail, dict) else [],
        http_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[dict[str, Any]] = []
    for err in exc.errors():
        details.append(
            {
                "loc": [str(loc) for loc in err.get("loc", [])],
                "field": str(err.get("loc", [])[-1]) if err.get("loc") else None,
                "message": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
        http_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        http_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
