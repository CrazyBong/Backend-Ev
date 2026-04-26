from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.db.database import create_db_engine, engine
from app.db.redis import init_redis_pool, close_redis_pool
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle management."""
    # ── Phase 10: Structured JSON logging — must be first ─────────────────────
    setup_logging()

    # ── Phase 10: Sentry APM — opt-in via SENTRY_DSN env var ─────────────────
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            environment=settings.ENVIRONMENT,
            integrations=[StarletteIntegration(), SqlalchemyIntegration()],
        )
        logger.info("Sentry APM initialised", extra={"traces_sample_rate": settings.SENTRY_TRACES_SAMPLE_RATE})

    logger.info("Starting EVChargeFinder API...")

    # Startup
    await init_redis_pool()
    await create_db_engine()

    import sys
    if "pytest" not in sys.modules:
        from app.tasks.scheduler import start_scheduler
        start_scheduler()

    logger.info("API ready", extra={"environment": settings.ENVIRONMENT})
    yield

    # Shutdown
    import sys
    if "pytest" not in sys.modules:
        from app.tasks.scheduler import shutdown_scheduler
        shutdown_scheduler()

    await close_redis_pool()
    await engine.dispose()
    logger.info("API shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVChargeFinder API",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── Middleware stack (outermost first) ────────────────────────────────────

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Phase 10: Prometheus request instrumentation
    from app.middleware.metrics import PrometheusMiddleware
    app.add_middleware(PrometheusMiddleware)

    # Correlation ID + process-time injection (outermost for full trace coverage)
    from app.middleware.correlation import CorrelationIdMiddleware
    app.add_middleware(CorrelationIdMiddleware)

    # Rate limiter
    from app.middleware.rate_limiter import RateLimiterMiddleware
    app.add_middleware(RateLimiterMiddleware)

    # Error handler (registered last so it wraps all routes)
    from app.middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.routers import (
        auth, stations, slots, bookings, payments,
        ws, notifications, reviews, routes, admin, demand,
        websockets, iot,
    )
    from app.routers.metrics import router as metrics_router  # Phase 10

    prefix = "/v1"
    app.include_router(metrics_router)                                                     # /metrics — no prefix, no auth
    app.include_router(auth.router,          prefix=f"{prefix}/auth",          tags=["auth"])
    app.include_router(stations.router,      prefix=f"{prefix}/stations",      tags=["stations"])
    app.include_router(slots.router,         prefix=f"{prefix}/slots",         tags=["slots"])
    app.include_router(bookings.router,      prefix=f"{prefix}/bookings",      tags=["bookings"])
    app.include_router(payments.router,      prefix=f"{prefix}/payments",      tags=["payments"])
    app.include_router(ws.router,            prefix=f"{prefix}/ws",            tags=["websocket"])
    app.include_router(notifications.router, prefix=f"{prefix}/notifications", tags=["notifications"])
    app.include_router(reviews.router,       prefix=f"{prefix}/reviews",       tags=["reviews"])
    app.include_router(routes.router,        prefix=f"{prefix}/routes",        tags=["routes"])
    app.include_router(admin.router,         prefix=f"{prefix}/admin",         tags=["admin"])
    app.include_router(demand.router,        prefix=f"{prefix}/demand",        tags=["demand"])
    app.include_router(websockets.router,    prefix=f"{prefix}/ws",            tags=["websockets"])
    app.include_router(iot.router,           prefix=f"{prefix}/iot",           tags=["iot", "hardware"])

    return app


app = create_app()

