"""
Prometheus metrics middleware.

Instruments every HTTP request with:
  - http_requests_total          (Counter)   — by method, path_template, status
  - http_request_duration_seconds (Histogram) — P50/P95/P99 latency
  - http_requests_in_progress    (Gauge)      — current in-flight count
"""
import time
import re
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

# ── Metric definitions (module-level singletons) ──────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "path"],
)


# Paths that should never be tracked (noisy / not useful)
_EXCLUDED_PATHS = re.compile(r"^/(metrics|health|favicon\.ico)")


def _resolve_path(request: Request) -> str:
    """
    Return the matched route path template (e.g. '/v1/bookings/{booking_id}')
    so high-cardinality UUID values are not exploded into separate metric series.
    """
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path  # type: ignore[attr-defined]
    return request.url.path  # fallback for unmatched (404) paths


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip noisy / internal paths
        if _EXCLUDED_PATHS.match(request.url.path):
            return await call_next(request)

        path = _resolve_path(request)
        method = request.method

        REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(method=method, path=path, status_code=500).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

        REQUEST_COUNT.labels(
            method=method, path=path, status_code=response.status_code
        ).inc()

        return response
