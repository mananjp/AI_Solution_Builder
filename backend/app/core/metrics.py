"""
AI Solution Builder — Prometheus Metrics

Lightweight request instrumentation plus health gauges.
Exposed via the /metrics endpoint (OpenMetrics text format).
"""

import time

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUESTS_TOTAL = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUESTS_INFLIGHT = Gauge("http_requests_inflight", "In-flight HTTP requests")
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
DB_HEALTH = Gauge("db_up", "Database reachability (1 = up)")
REDIS_HEALTH = Gauge("redis_up", "Redis reachability (1 = up)")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts/latency for Prometheus scraping."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in ("/metrics", "/health", "/ready"):
            return await call_next(request)

        REQUESTS_INFLIGHT.inc()
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            REQUESTS_TOTAL.labels(request.method, request.url.path, "500").inc()
            raise
        finally:
            REQUESTS_INFLIGHT.dec()

        REQUEST_DURATION.labels(request.method, request.url.path).observe(time.monotonic() - start)
        REQUESTS_TOTAL.labels(request.method, request.url.path, str(response.status_code)).inc()
        return response


def set_db_health(up: bool) -> None:
    DB_HEALTH.set(1 if up else 0)


def set_redis_health(up: bool) -> None:
    REDIS_HEALTH.set(1 if up else 0)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
