"""
/metrics — Prometheus scrape endpoint.

This route is intentionally unauthenticated and excluded from rate limiting.
It should be protected at the infrastructure layer (e.g. ingress allow-list)
and never exposed to the public internet directly.
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics_endpoint() -> PlainTextResponse:
    """Prometheus text-format metrics scrape endpoint."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
