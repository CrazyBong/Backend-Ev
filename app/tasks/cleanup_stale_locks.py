"""
Stale Slot Lock Cleaner — Phase 6
Lock-expiry-first strategy:
1. Update locked_until-expired slots → AVAILABLE
2. Release corresponding Redis keys
3. Cancel PENDING_PAYMENT bookings for freed slots
Runs every 30 seconds via APScheduler.
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis

logger = logging.getLogger(__name__)


async def release_stale_slot_locks(db: AsyncSession):
    """
    Release LOCKED slots where locked_until has passed.
    Uses DB-first authoritative check to avoid Redis drift.
    """
    redis = await get_redis()

    # Step 1: Free expired slot locks atomically, returning affected IDs
    result = await db.execute(text("""
        UPDATE slots
        SET status = 'AVAILABLE',
            locked_by_user = NULL,
            locked_until = NULL,
            updated_at = NOW()
        WHERE status = 'LOCKED'
          AND locked_until < NOW()
        RETURNING id, station_id
    """))
    released = result.fetchall()

    if not released:
        return 0

    slot_ids = [str(row.id) for row in released]

    # Step 2: Delete Redis TTL locks for freed slots
    redis_keys = [f"slot_lock:{sid}" for sid in slot_ids]
    if redis_keys:
        await redis.delete(*redis_keys)

    # Step 3: Cancel associated PENDING_PAYMENT bookings
    await db.execute(text("""
        UPDATE bookings
        SET status = 'CANCELLED_BY_ADMIN',
            cancellation_reason = 'Payment timeout — slot lock expired',
            updated_at = NOW()
        WHERE slot_id = ANY(:slot_ids::uuid[])
          AND status = 'PENDING_PAYMENT'
    """), {"slot_ids": slot_ids})

    await db.commit()

    logger.info(f"[StaleLocksClean] Released {len(released)} stale slot locks, slots: {slot_ids}")
    return len(released)
