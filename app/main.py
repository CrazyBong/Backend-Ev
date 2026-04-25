from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.db.database import create_db_engine, engine
from app.db.redis import init_redis_pool, close_redis_pool
# Placeholder imports for routers and middleware
# These will be implemented in subsequent steps
# from app.middleware.error_handler import register_error_handlers
# from app.middleware.request_logger import RequestLoggerMiddleware
# from app.routers import auth, stations, slots, bookings, payments, routes, reviews, notifications, admin

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle management."""
    logger.info("Starting EVChargeFinder API...")

    # Startup
    await init_redis_pool()
    await create_db_engine()
    
    import sys
    if "pytest" not in sys.modules:
        from app.tasks.scheduler import start_scheduler
        start_scheduler()

    logger.info(f"API ready — Environment: {settings.ENVIRONMENT}")
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

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handler (registered first so it wraps all routes)
    from app.middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # Correlation ID (outermost for maximum tracing)
    from app.middleware.correlation import CorrelationIdMiddleware
    app.add_middleware(CorrelationIdMiddleware)

    # Rate limiter
    from app.middleware.rate_limiter import RateLimiterMiddleware
    app.add_middleware(RateLimiterMiddleware)

    from app.routers import auth, stations, slots, bookings, payments, ws, notifications, reviews, routes, admin, demand

    prefix = "/v1"
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

    return app


app = create_app()
