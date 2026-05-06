import pytest
import hmac
import hashlib
import json
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import text
from app.config import settings
from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def mock_razorpay():
    with patch(
        "app.services.booking_service.razorpay_client.order.create",
        side_effect=lambda *a, **kw: {"id": f"order_{uuid4().hex[:10]}"},
    ) as mocked_order_create:
        yield mocked_order_create

def compute_webhook_signature(payload_body: str) -> str:
    return hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

class TestWebhook:
    async def test_invalid_webhook_signature_rejected(self, client):
        payload = json.dumps({"event": "payment.captured"})
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": "invalid_sig", "Content-Type": "application/json"}
        )
        assert res.status_code == 422
    
    async def test_valid_webhook_silent_ignore_missing_order(self, client):
        payload = json.dumps({
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test123",
                        "order_id": "order_nonexistent"
                    }
                }
            }
        })
        signature = compute_webhook_signature(payload)
        res = await client.post("/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"}
        )
        assert res.status_code == 200

    async def test_valid_webhook_confirms_pending_booking(self, client, db_session, seed_user, seed_slot):
        auth = await get_auth_headers(seed_user)
        booking_res = await client.post(
            "/v1/bookings",
            json={
                "slot_id": str(seed_slot.id),
                "scheduled_start": "2026-06-03T14:00:00Z",
                "scheduled_end": "2026-06-03T15:00:00Z",
            },
            headers={**auth, "Idempotency-Key": str(uuid4())},
        )

        assert booking_res.status_code == 200
        order_id = booking_res.json()["data"]["razorpay_order_id"]
        booking_id = booking_res.json()["data"]["booking_id"]

        payload = json.dumps({
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_confirmed",
                        "order_id": order_id
                    }
                }
            }
        })
        signature = compute_webhook_signature(payload)
        res = await client.post(
            "/v1/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"}
        )
        assert res.status_code == 200

        booking_row = await db_session.execute(
            text("SELECT status FROM bookings WHERE id = :booking_id"),
            {"booking_id": booking_id}
        )
        assert booking_row.scalar() == "CONFIRMED"

        slot_row = await db_session.execute(
            text("SELECT status FROM slots WHERE id = :slot_id"),
            {"slot_id": str(seed_slot.id)}
        )
        assert slot_row.scalar() == "BOOKED"

        payment_row = await db_session.execute(
            text("SELECT status, webhook_verified FROM payments WHERE razorpay_order_id = :order_id"),
            {"order_id": order_id}
        )
        payment = payment_row.mappings().first()
        assert payment["status"] == "SUCCESS"
        assert payment["webhook_verified"] is True
