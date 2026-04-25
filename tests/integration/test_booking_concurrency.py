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
        self, client, seed_user, seed_station_admin, seed_slot
    ):
        """
        Two concurrent requests for the exact same slot in the exact same time window.
        Exactly one should get 200/201 (since we return {"data": ...}), the other should get a 409 Conflict.
        """
        # Get Auth headers for two different users
        from tests.conftest import get_auth_headers
        auth_1 = await get_auth_headers(seed_user)
        auth_2 = await get_auth_headers(seed_station_admin)

        slot_id = seed_slot.id

        payload1 = {
            "slot_id": str(slot_id),
            "scheduled_start": "2026-06-01T14:00:00Z",
            "scheduled_end":   "2026-06-01T14:45:00Z",
        }
        
        payload2 = {
            "slot_id": str(slot_id),
            "scheduled_start": "2026-06-01T14:00:00Z",
            "scheduled_end":   "2026-06-01T14:45:00Z",
        }

        # Fire both requests simultaneously
        res1, res2 = await asyncio.gather(
            client.post("/v1/bookings", json=payload1, headers={**auth_1, "Idempotency-Key": str(uuid4())}),
            client.post("/v1/bookings", json=payload2, headers={**auth_2, "Idempotency-Key": str(uuid4())}),
        )

        statuses = {res1.status_code, res2.status_code}
        assert 200 in statuses, f"At least one booking must succeed. Got {res1.status_code}, {res2.status_code}. Bodies: {res1.json()}, {res2.json()}"
        assert 409 in statuses, "At least one booking must fail due to lock."
        
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
