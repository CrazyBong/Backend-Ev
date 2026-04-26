import pytest
import asyncio
from uuid import uuid4
from unittest.mock import patch

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def mock_razorpay():
    with patch("app.services.booking_service.razorpay_client.order.create", side_effect=lambda *a, **kw: {"id": f"order_{uuid4().hex[:10]}"}) as m:
        yield m

class TestBookingConcurrency:
    async def test_concurrent_booking_same_slot_one_wins(
        self, seed_slot, seed_user, seed_station_admin
    ):
        from app.db.database import get_db, get_db_read
        from app.config import settings
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from tests.conftest import get_auth_headers

        concurrent_engine = create_async_engine(settings.DATABASE_URL_ASYNC, pool_size=3, max_overflow=5)
        ConcurrentSession = async_sessionmaker(bind=concurrent_engine, class_=AsyncSession, expire_on_commit=False)

        async def _concurrent_get_db():
            async with ConcurrentSession() as session:
                yield session

        app.dependency_overrides[get_db] = _concurrent_get_db
        app.dependency_overrides[get_db_read] = _concurrent_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as concurrent_client:
                auth_1 = await get_auth_headers(seed_user)
                auth_2 = await get_auth_headers(seed_station_admin)
                
                payload1 = {
                    "slot_id": str(seed_slot.id),
                    "scheduled_start": "2026-06-01T14:00:00Z",
                    "scheduled_end":   "2026-06-01T14:45:00Z",
                }
                payload2 = {
                    "slot_id": str(seed_slot.id),
                    "scheduled_start": "2026-06-01T14:15:00Z",
                    "scheduled_end":   "2026-06-01T15:00:00Z",
                }
        
                res1, res2 = await asyncio.gather(
                    concurrent_client.post("/v1/bookings", headers={**auth_1, "Idempotency-Key": str(uuid4())}, json=payload1),
                    concurrent_client.post("/v1/bookings", headers={**auth_2, "Idempotency-Key": str(uuid4())}, json=payload2)
                )
        finally:
            app.dependency_overrides.clear()
            await concurrent_engine.dispose()

        statuses = {res1.status_code, res2.status_code}
        assert 200 in statuses, f"At least one booking must succeed. Got {res1.status_code}, {res2.status_code}. Bodies: {res1.json()}, {res2.json()}"
        assert 409 in statuses, f"At least one booking must fail due to lock. Got statuses: {statuses}"
        
    async def test_idempotency_key_prevents_duplicate_booking(self, client, seed_user, seed_slot_2):
        from tests.conftest import get_auth_headers
        auth = await get_auth_headers(seed_user)
        key = str(uuid4())
        
        payload = {
            "slot_id": str(seed_slot_2.id),
            "scheduled_start": "2026-06-02T14:00:00Z",
            "scheduled_end": "2026-06-02T14:45:00Z",
        }
        
        res1 = await client.post("/v1/bookings", json=payload, headers={**auth, "Idempotency-Key": key})
        res2 = await client.post("/v1/bookings", json=payload, headers={**auth, "Idempotency-Key": key})

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["data"]["booking_id"] == res2.json()["data"]["booking_id"]
