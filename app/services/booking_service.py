import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.redis import get_redis
from app.utils.razorpay_client import razorpay_client

from fastapi.concurrency import run_in_threadpool

SLOT_LOCK_KEY = "slot_lock:{slot_id}"
IDEMPOTENCY_KEY = "idem:{key}"

async def create_booking(
    user_id: str,
    slot_id: str,
    scheduled_start: datetime,
    scheduled_end: datetime,
    idempotency_key: str,
    db: AsyncSession,
) -> dict:
    redis = await get_redis()
    
    # Check Idempotency Key
    idem_cache_key = IDEMPOTENCY_KEY.format(key=idempotency_key)
    existing = await redis.get(idem_cache_key)
    if existing:
        val = existing.decode("utf-8") if isinstance(existing, bytes) else existing
        return json.loads(val)

    # Validate Time Window
    now = datetime.now(timezone.utc)
    # Ensure scheduled start/end match expected types/naive behavior if needed.
    # We will assume they are timezone-aware.
    if scheduled_start.tzinfo is None:
        scheduled_start = scheduled_start.replace(tzinfo=timezone.utc)
    if scheduled_end.tzinfo is None:
        scheduled_end = scheduled_end.replace(tzinfo=timezone.utc)

    if scheduled_start <= now:
        raise HTTPException(status_code=400, detail={"code": "PAST_TIME_WINDOW", "message": "Booking start time must be in the future."})
    if scheduled_end <= scheduled_start:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TIME_WINDOW", "message": "End time must be after start time."})
    
    duration = (scheduled_end - scheduled_start).total_seconds()
    if duration < 1800:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TIME_WINDOW", "message": "Minimum duration is 30 minutes."})
    if duration > 7200:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TIME_WINDOW", "message": "Maximum duration is 2 hours."})

    # Quick read for slot info out-of-band to prepare external api call (amount calculation)
    slot_info_result = await db.execute(text("""
        SELECT s.id, s.station_id, s.charger_type, s.power_kw,
               st.price_per_unit, st.price_per_hour, st.operating_hours
        FROM slots s
        JOIN stations st ON st.id = s.station_id
        WHERE s.id = :slot_id
    """), {"slot_id": slot_id})
    slot_info = slot_info_result.mappings().first()
    await db.commit() # End implicit transaction
    
    if not slot_info:
        raise HTTPException(status_code=404, detail={"code": "SLOT_NOT_FOUND", "message": "Slot not found."})

    _validate_operating_hours(slot_info.get("operating_hours"), scheduled_start, scheduled_end)

    amount = _calculate_amount(
        scheduled_start=scheduled_start, scheduled_end=scheduled_end,
        price_per_unit=slot_info["price_per_unit"], price_per_hour=slot_info["price_per_hour"],
        power_kw=slot_info["power_kw"],
    )

    # 5. External API Call (Outside Transaction, non-blocking)
    razorpay_order = await run_in_threadpool(
        razorpay_client.order.create,
        {
            "amount": int(amount * 100),
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "slot_id": str(slot_id),
                "user_id": str(user_id),
                "station_id": str(slot_info["station_id"]),
            }
        }
    )

    async with db.begin():
        # Step 4: Postgres Row-Level Lock
        slot_result = await db.execute(text("""
            SELECT s.status, s.locked_until, st.is_active
            FROM slots s
            JOIN stations st ON st.id = s.station_id
            WHERE s.id = :slot_id
            FOR UPDATE
        """), {"slot_id": slot_id})
        slot = slot_result.mappings().first()

        if not slot:
            raise HTTPException(status_code=404, detail={"code": "SLOT_NOT_FOUND", "message": "Slot not found."})
        if not slot["is_active"]:
            raise HTTPException(status_code=409, detail={"code": "SLOT_UNAVAILABLE", "message": "Station is inactive."})
        if slot["status"] == "OFFLINE":
            raise HTTPException(status_code=409, detail={"code": "SLOT_UNAVAILABLE", "message": "Slot is offline."})
        if slot["status"] in ("BOOKED", "IN_USE"):
            raise HTTPException(status_code=409, detail={"code": "SLOT_UNAVAILABLE", "message": "Slot is already booked or in use."})
        if slot["status"] == "LOCKED":
            locked_until = slot["locked_until"]
            if locked_until and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until and locked_until > now:
                raise HTTPException(status_code=409, detail={"code": "SLOT_LOCKED", "message": "Slot is temporarily reserved by another user."})

        # Overlapping Bookings Check
        overlap = await db.execute(text("""
            SELECT id FROM bookings
            WHERE slot_id = :slot_id
            AND status IN ('PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE')
            AND scheduled_start < :end_time
            AND scheduled_end > :start_time
            LIMIT 1
        """), {
            "slot_id": slot_id,
            "start_time": scheduled_start,
            "end_time": scheduled_end,
        })
        if overlap.first():
            raise HTTPException(status_code=409, detail={"code": "SLOT_UNAVAILABLE", "message": "Overlapping booking exists for this time window."})

        # Redis distributed lock for dual-protection during transaction
        lock_key = SLOT_LOCK_KEY.format(slot_id=slot_id)
        lock_acquired = await redis.set(lock_key, user_id, nx=True, ex=settings.SLOT_LOCK_TTL_SECONDS)
        
        if not lock_acquired:
            existing_lock = await redis.get(lock_key)
            if existing_lock and existing_lock.decode("utf-8") != user_id:
               raise HTTPException(status_code=409, detail={"code": "SLOT_LOCKED", "message": "Slot is temporarily reserved."})

        # DB locking and update
        lock_expires_at = now + timedelta(seconds=settings.SLOT_LOCK_TTL_SECONDS)
        await db.execute(text("""
            UPDATE slots
            SET status = 'LOCKED',
                locked_by_user = :user_id,
                locked_until = :locked_until,
                updated_at = NOW()
            WHERE id = :slot_id
        """), {
            "slot_id": slot_id,
            "user_id": user_id,
            "locked_until": lock_expires_at,
        })

        booking_id = str(uuid4())
        qr_payload = f"EVCF:{booking_id}:{slot_id}"

        await db.execute(text("""
            INSERT INTO bookings (
                id, user_id, slot_id, station_id, status,
                scheduled_start, scheduled_end, amount, qr_code, idempotency_key
            ) VALUES (
                :id, :user_id, :slot_id, :station_id, 'PENDING_PAYMENT',
                :scheduled_start, :scheduled_end, :amount, :qr_code, :idempotency_key
            )
        """), {
            "id": booking_id,
            "user_id": user_id,
            "slot_id": slot_id,
            "station_id": slot_info["station_id"],
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "amount": amount,
            "qr_code": qr_payload,
            "idempotency_key": idempotency_key,
        })

        await db.execute(text("""
            INSERT INTO payments (booking_id, user_id, razorpay_order_id, amount)
            VALUES (:booking_id, :user_id, :order_id, :amount)
        """), {
            "booking_id": booking_id,
            "user_id": user_id,
            "order_id": razorpay_order["id"],
            "amount": amount,
        })

    response = {
        "booking_id": booking_id,
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount,
        "lock_expires_at": lock_expires_at.isoformat(),
    }
    
    await redis.setex(idem_cache_key, 86400, json.dumps(response))

    return response


def _validate_operating_hours(operating_hours: dict | None, start: datetime, end: datetime):
    if not operating_hours:
        operating_hours = {}
        
    open_time_str = operating_hours.get("open", "00:00")
    close_time_str = operating_hours.get("close", "23:59")
    open_days = operating_hours.get("days", list(range(1, 8)))

    if start.isoweekday() not in open_days:
        raise HTTPException(status_code=400, detail={"code": "STATION_CLOSED", "message": "Station is closed on this day."})

    try:
        open_h, open_m = map(int, open_time_str.split(":"))
        close_h, close_m = map(int, close_time_str.split(":"))
    except Exception:
        open_h, open_m = 0, 0
        close_h, close_m = 23, 59

    station_open1 = start.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    station_close1 = station_open1.replace(hour=close_h, minute=close_m)

    if station_close1 < station_open1:
        station_close1 += timedelta(days=1)

    # Calculate previous day's shift as well for midnight wrapping edge cases
    station_open2 = station_open1 - timedelta(days=1)
    station_close2 = station_close1 - timedelta(days=1)

    valid1 = (station_open1 <= start) and (end <= station_close1)
    valid2 = (station_open2 <= start) and (end <= station_close2)

    if not (valid1 or valid2):
        raise HTTPException(status_code=400, detail={"code": "STATION_CLOSED", "message": "Booking is outside operating hours."})


def _calculate_amount(scheduled_start: datetime, scheduled_end: datetime, price_per_unit, price_per_hour, power_kw) -> float:
    duration_hours = (scheduled_end - scheduled_start).total_seconds() / 3600

    if price_per_unit:
        estimated_kwh = float(power_kw) * duration_hours * 0.85
        return round(float(price_per_unit) * estimated_kwh, 2)
    elif price_per_hour:
        return round(float(price_per_hour) * duration_hours, 2)
    else:
        return round(10.0 * duration_hours, 2)
