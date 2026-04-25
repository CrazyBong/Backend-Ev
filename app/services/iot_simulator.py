"""
IoT Simulator — Phase 6
Simulates real-time charger slot lifecycle transitions:
  IN_USE → AVAILABLE  (session ends)
  AVAILABLE → IN_USE  (walk-in user starts charging)
This creates a realistic live-data stream for demo/dev purposes.
Supabase Realtime picks up DB changes and broadcasts to clients.
"""
import asyncio
import random
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def simulate_session_end(db: AsyncSession):
    """
    Picks a random IN_USE slot and transitions it to AVAILABLE.
    Called scheduledevery 30–90 seconds by APScheduler.
    """
    result = await db.execute(text("""
        SELECT id, station_id FROM slots
        WHERE status = 'IN_USE'
        ORDER BY RANDOM()
        LIMIT 1
    """))
    slot = result.mappings().first()

    if not slot:
        return  # No active sessions to simulate

    await db.execute(text("""
        UPDATE slots
        SET status = 'AVAILABLE',
            updated_at = NOW()
        WHERE id = :id
    """), {"id": slot["id"]})
    await db.commit()
    logger.info(f"[IoT] Simulated session end — slot {slot['id']} → AVAILABLE")


async def simulate_walk_in_session(db: AsyncSession):
    """
    Picks a random AVAILABLE slot and transitions it to IN_USE.
    Simulates a walk-in user plugging in without a reservation.
    """
    result = await db.execute(text("""
        SELECT id, station_id FROM slots
        WHERE status = 'AVAILABLE'
        ORDER BY RANDOM()
        LIMIT 1
    """))
    slot = result.mappings().first()

    if not slot:
        return

    await db.execute(text("""
        UPDATE slots
        SET status = 'IN_USE',
            updated_at = NOW()
        WHERE id = :id
    """), {"id": slot["id"]})
    await db.commit()
    logger.info(f"[IoT] Simulated walk-in — slot {slot['id']} → IN_USE")
