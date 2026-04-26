from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
from app.config import settings
import logging
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Read replica engine (fall back to primary if not provided)
engine_ro = create_async_engine(
    settings.DATABASE_URL_RO_ASYNC or settings.DATABASE_URL_ASYNC,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocalRO = async_sessionmaker(
    bind=engine_ro,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Prometheus DB-pool health gauges ---------------------------------------

_DB_POOL_SIZE = Gauge("db_pool_size", "SQLAlchemy connection pool size", ["pool"])
_DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Active DB connections checked out from the pool", ["pool"])
_DB_POOL_OVERFLOW = Gauge("db_pool_overflow", "Number of connections opened beyond pool_size", ["pool"])


def _register_pool_events(eng, pool_name: str) -> None:
    """Attach SQLAlchemy pool events to refresh Prometheus gauges on checkout/checkin."""
    @event.listens_for(eng.sync_engine, "checkout")
    def on_checkout(dbapi_conn, conn_record, conn_proxy):
        pool = eng.sync_engine.pool
        _DB_POOL_SIZE.labels(pool=pool_name).set(pool.size())
        _DB_POOL_CHECKED_OUT.labels(pool=pool_name).set(pool.checkedout())
        _DB_POOL_OVERFLOW.labels(pool=pool_name).set(pool.overflow())

    @event.listens_for(eng.sync_engine, "checkin")
    def on_checkin(dbapi_conn, conn_record):
        pool = eng.sync_engine.pool
        _DB_POOL_SIZE.labels(pool=pool_name).set(pool.size())
        _DB_POOL_CHECKED_OUT.labels(pool=pool_name).set(pool.checkedout())
        _DB_POOL_OVERFLOW.labels(pool=pool_name).set(pool.overflow())


_register_pool_events(engine, "primary")
_register_pool_events(engine_ro, "replica")

class Base(DeclarativeBase):
    pass

async def create_db_engine():
    """Verify database connection on startup."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise e

async def get_db():
    """
    Dependency for getting async database session.
    Auto-commit is DISABLED to prevent data corruption on partial service failures.
    Mutations must use `async with db.begin()` for atomicity.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_db_read():
    """
    Dependency for getting async database session directed at the read replica.
    Use exclusively for GET endpoints to scale read query throughput.
    """
    async with AsyncSessionLocalRO() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
