import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

async def release_abandoned_locks(db: AsyncSession):
    """
    Finds bookings stuck in PENDING_PAYMENT longer than the lock TTL.
    Transitions booking to CANCELLED_BY_SYSTEM and reverts the slot to AVAILABLE.
    """
    try:
        # We use a single query with a CTE to ensure atomicity.
        # This prevents a scenario where bookings are updated but slots are not.
        query = text(f"""
            WITH expired_bookings AS (
                UPDATE bookings
                SET status = 'CANCELLED_BY_ADMIN',
                    cancellation_reason = 'Payment timeout',
                    updated_at = NOW()
                WHERE status = 'PENDING_PAYMENT'
                  AND created_at < NOW() - INTERVAL '{settings.SLOT_LOCK_TTL_SECONDS} seconds'
                RETURNING id, slot_id
            )
            UPDATE slots s
            SET status = 'AVAILABLE',
                locked_by_user = NULL,
                locked_until = NULL,
                updated_at = NOW()
            FROM expired_bookings eb
            WHERE s.id = eb.slot_id
            RETURNING s.id, eb.id as booking_id;
        """)
        result = await db.execute(query)
        released = result.fetchall()
        await db.commit()
        
        if released:
            logger.info(f"Released abandoned locks for {len(released)} bookings.")
            
    except Exception as e:
        logger.error(f"Error releasing abandoned locks: {str(e)}")
        await db.rollback()

async def cleanup_database_garbage(db: AsyncSession):
    """
    Runs the Postgres functions to clean up expired OTPs and JWT blacklists.
    """
    try:
        await db.execute(text("SELECT cleanup_expired_otps();"))
        await db.execute(text("SELECT cleanup_jwt_blacklist();"))
        await db.commit()
    except Exception as e:
        logger.error(f"Error cleaning up database garbage: {str(e)}")
        await db.rollback()
