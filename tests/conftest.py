import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.main import app
from app.db.database import get_db, get_db_read, Base
from app.db.redis import get_redis, init_redis_pool, close_redis_pool
from app.services.auth_service import create_access_token

# Import models to register them with Base.metadata
from app.models.user import User
from app.models.station import Station
from app.models.slot import Slot
from app.models.review import Review
from app.models.booking import Booking
from app.models.notification import Notification


# ─── Database: Setup schema + Per-test engine/session for isolation ──────────

@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure tables exist in the test database.
    Using function scope to avoid ScopeMismatch with function-scoped loops.
    PostgreSQL CREATE IF NOT EXISTS is fast enough for integration tests.
    """
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, echo=False)
    if engine:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
            # Truncate all tables to ensure isolation
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        await engine.dispose()


@pytest.fixture
async def db_session():
    """Provides a fresh database session and ensures engine disposal."""
    test_engine = create_async_engine(settings.DATABASE_URL_ASYNC, echo=False)
    Session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with Session() as session:
        yield session
        await session.rollback()
        
    await test_engine.dispose()


# ─── Redis: Fresh pool + clean slate per test ─────────────────────────────────

@pytest.fixture(autouse=True)
async def clean_redis():
    """Initialise a fresh Redis pool for each test and flush the DB."""
    await init_redis_pool()
    redis = await get_redis()
    if redis:
        await redis.flushdb()
    yield
    await close_redis_pool()


# ─── HTTPX async client with dependency overrides ──────────────────────────────

@pytest.fixture
async def client(db_session):
    """Client with DB dependency overridden to use the per-test session."""
    async def _override_get_db():
        # Do not use a try/finally rollback here because the db_session fixture 
        # already handles the rollback, and FastAPI dependency teardown may execute concurrently with it.
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_db_read] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Misc fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def freeze_time():
    import freezegun
    with freezegun.freeze_time("2026-04-20 12:00:00") as frozen_time:
        yield frozen_time


@pytest.fixture
async def auth_headers():
    """JWT access token for a fake user (no DB required)."""
    class _FakeUser:
        id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        role = "user"
    return await get_auth_headers(_FakeUser())
        
async def get_auth_headers(user):
    from app.services.auth_service import create_access_token
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}

import random

@pytest.fixture
async def seed_user(db_session):
    user_id = uuid.uuid4()
    phone = f"+9199{random.randint(10000000, 99999999)}"
    await db_session.execute(text("""
        INSERT INTO users (id, phone, role, is_active) VALUES (:id, :phone, 'user', true)
    """), {"id": str(user_id), "phone": phone})
    await db_session.commit()
    class _U:
        id = user_id
        phone_no = phone
        role = "user"
    return _U()

@pytest.fixture
async def seed_station_admin(db_session):
    user_id = uuid.uuid4()
    phone = f"+9188{random.randint(10000000, 99999999)}"
    await db_session.execute(text("""
        INSERT INTO users (id, phone, role, is_active) VALUES (:id, :phone, 'station_admin', true)
    """), {"id": str(user_id), "phone": phone})
    await db_session.commit()
    class _U:
        id = user_id
        phone_no = phone
        role = "station_admin"
    return _U()

@pytest.fixture
async def seed_slot(db_session, seed_station_admin):
    station_id = uuid.uuid4()
    import json
    await db_session.execute(text("""
        INSERT INTO stations (id, name, network, location, address, operating_hours, admin_user_id, price_per_unit, is_active, total_slots, available_slots)
        VALUES (:id, 'Test Station', 'TATA_POWER', ST_GeomFromText('POINT(77.4126 23.2599)', 4326), :address, :hours, :admin_id, 15.0, true, 10, 10)
    """), {
        "id": str(station_id),
        "address": json.dumps({"street": "123 Main St"}),
        "hours": json.dumps({"open":"00:00", "close":"23:59", "days":[1,2,3,4,5,6,7]}),
        "admin_id": str(seed_station_admin.id)
    })
    
    # Link station admin in station_managers table
    await db_session.execute(text("""
        INSERT INTO station_managers (user_id, station_id)
        VALUES (:user_id, :station_id)
    """), {"user_id": str(seed_station_admin.id), "station_id": str(station_id)})
    
    slot_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO slots (id, station_id, slot_number, charger_type, power_kw, status)
        VALUES (:id, :station_id, 1, 'CCS2', 50.0, 'AVAILABLE')
    """), {"id": str(slot_id), "station_id": str(station_id)})
    await db_session.commit()
    class _S:
        pass
    s = _S()
    s.id = slot_id
    s.station_id = station_id
    return s

@pytest.fixture
async def seed_slot_2(db_session, seed_slot):
    slot_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO slots (id, station_id, slot_number, charger_type, power_kw, status)
        VALUES (:id, :station_id, 2, 'CCS2', 50.0, 'AVAILABLE')
    """), {"id": str(slot_id), "station_id": str(seed_slot.station_id)})
    await db_session.commit()
    class _S:
        pass
    s = _S()
    s.id = slot_id
    s.station_id = seed_slot.station_id
    return s
