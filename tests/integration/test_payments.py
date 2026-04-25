import pytest
import hmac
import hashlib
import json
from app.config import settings

pytestmark = pytest.mark.asyncio

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
