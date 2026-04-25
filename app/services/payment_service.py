import hashlib
import hmac
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.redis import get_redis

def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_webhook_signature(payload_body: bytes, received_signature: str) -> bool:
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)

async def confirm_booking_by_order(razorpay_order_id: str, payment_id: str, db: AsyncSession):
    redis = await get_redis()
    async with db.begin():
        result = await db.execute(text("""
            SELECT b.id, b.status, b.user_id, b.slot_id, b.station_id,
                   b.scheduled_start, b.scheduled_end, b.amount, b.qr_code,
                   p.id as payment_id_pk, p.status as payment_status
            FROM payments p
            JOIN bookings b ON b.id = p.booking_id
            WHERE p.razorpay_order_id = :order_id
            FOR UPDATE OF b, p
        """), {"order_id": razorpay_order_id})
        booking = result.mappings().first()

        if not booking:
            return

        booking_id = str(booking["id"])

        if booking["status"] == "CONFIRMED":
            return

        if booking["status"] not in ("PENDING_PAYMENT",):
            return

        await db.execute(text("""
            UPDATE bookings
            SET status = 'CONFIRMED', updated_at = NOW()
            WHERE id = :id
        """), {"id": booking_id})

        await db.execute(text("""
            UPDATE slots
            SET status = 'BOOKED',
                locked_by_user = NULL,
                locked_until = NULL,
                updated_at = NOW()
            WHERE id = :slot_id
        """), {"slot_id": booking["slot_id"]})

        await db.execute(text("""
            UPDATE payments
            SET status = 'SUCCESS',
                razorpay_payment_id = :payment_id,
                webhook_verified = TRUE,
                webhook_received_at = NOW(),
                updated_at = NOW()
            WHERE razorpay_order_id = :order_id
        """), {"order_id": razorpay_order_id, "payment_id": payment_id})

    lock_key = f"slot_lock:{booking['slot_id']}"
    await redis.delete(lock_key)


    # push_service = getattr(app, "push_service", None)
    # trigger it in another Phase, or rely on a DB trigger or job queue.

async def process_refund(booking_id: str, reason: str, db, razorpay_client):
    result = await db.execute(text("""
        SELECT p.razorpay_payment_id, b.scheduled_start, b.amount
        FROM payments p
        JOIN bookings b ON b.id = p.booking_id
        WHERE p.booking_id = :booking_id AND p.status = 'SUCCESS'
    """), {"booking_id": booking_id})
    payment = result.mappings().first()

    if not payment:
        return None

    # Handle timezone naive
    scheduled_start = payment["scheduled_start"]
    if scheduled_start.tzinfo is None:
         scheduled_start = scheduled_start.replace(tzinfo=timezone.utc)

    refund_amount = _calculate_refund_amount(
        scheduled_start=scheduled_start,
        total_amount=float(payment["amount"])
    )

    if refund_amount > 0:
        refund = razorpay_client.payment.refund(
            payment["razorpay_payment_id"],
            {"amount": int(refund_amount * 100)}
        )
        return refund
    return None

def _calculate_refund_amount(scheduled_start: datetime, total_amount: float) -> float:
    now = datetime.now(timezone.utc)
    hours_until = (scheduled_start - now).total_seconds() / 3600

    if hours_until > 6:
        return total_amount
    elif hours_until >= 2:
        return total_amount * 0.5
    else:
        return 0.0
