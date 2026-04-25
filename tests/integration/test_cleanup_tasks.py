import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

from app.tasks.cleanup_tasks import release_abandoned_locks
from app.config import settings

pytestmark = pytest.mark.asyncio

class TestCleanupTasks:
    async def test_release_abandoned_locks(self, db_session, seed_user, seed_station_admin, seed_slot_2):
        # 1. Create a "PENDING_PAYMENT" booking that is OLDER than TTL
        old_booking_id = str(uuid4())
        old_time = datetime.now(timezone.utc) - timedelta(seconds=settings.SLOT_LOCK_TTL_SECONDS + 10)
        
        # 2. Create a "PENDING_PAYMENT" booking that is NEWER than TTL
        fresh_booking_id = str(uuid4())
        fresh_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        
        # 3. Create a secondary slot for the fresh booking, to avoid PK/Unique clashes
        fresh_slot_id = str(uuid4())
        await db_session.execute(text("""
            INSERT INTO slots (id, station_id, slot_number, charger_type, power_kw, status, locked_by_user, locked_until)
            VALUES (:id, :station_id, 999, 'CCS2', 50.0, 'LOCKED', :user_id, NOW() + INTERVAL '2 minutes')
        """), {"id": fresh_slot_id, "station_id": str(seed_slot_2.station_id), "user_id": str(seed_user.id)})
        
        # Manually lock seed_slot_2 to simulate locked status
        await db_session.execute(text("""
            UPDATE slots SET status = 'LOCKED', locked_by_user = :user_id, locked_until = NOW() + INTERVAL '1 minutes'
            WHERE id = :id
        """), {"id": str(seed_slot_2.id), "user_id": str(seed_user.id)})

        await db_session.execute(text("""
            INSERT INTO bookings (id, user_id, slot_id, station_id, status, scheduled_start, scheduled_end, amount, idempotency_key, created_at)
            VALUES 
            (:old_id, :user_id, :old_slot, :station_id, 'PENDING_PAYMENT', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 1 hour', 10.0, :idem_old, :old_time),
            (:fresh_id, :user_id, :fresh_slot, :station_id, 'PENDING_PAYMENT', NOW() + INTERVAL '2 day', NOW() + INTERVAL '2 day 1 hour', 10.0, :idem_fresh, :fresh_time)
        """), {
            "old_id": old_booking_id,
            "fresh_id": fresh_booking_id,
            "user_id": str(seed_user.id),
            "old_slot": str(seed_slot_2.id),
            "fresh_slot": fresh_slot_id,
            "station_id": str(seed_slot_2.station_id),
            "old_time": old_time,
            "idem_old": str(uuid4()),
            "idem_fresh": str(uuid4()),
            "fresh_time": fresh_time,
        })
        await db_session.commit()
        
        # Run the cleanup task
        await release_abandoned_locks(db_session)
        
        # Verify old booking is cancelled
        old_b = await db_session.execute(text("SELECT status FROM bookings WHERE id = :id"), {"id": old_booking_id})
        assert old_b.scalar() == "CANCELLED_BY_ADMIN"
        
        # Verify old slot is available and locks removed
        old_s = await db_session.execute(text("SELECT status, locked_by_user, locked_until FROM slots WHERE id = :id"), {"id": str(seed_slot_2.id)})
        s_row = old_s.mappings().first()
        assert s_row["status"] == "AVAILABLE"
        assert s_row["locked_by_user"] is None
        assert s_row["locked_until"] is None
        
        # Verify fresh booking is untouched
        fresh_b = await db_session.execute(text("SELECT status FROM bookings WHERE id = :id"), {"id": fresh_booking_id})
        assert fresh_b.scalar() == "PENDING_PAYMENT"
        
        # Verify fresh slot is still locked
        fresh_s = await db_session.execute(text("SELECT status, locked_by_user FROM slots WHERE id = :id"), {"id": fresh_slot_id})
        fs_row = fresh_s.mappings().first()
        assert fs_row["status"] == "LOCKED"
        assert fs_row["locked_by_user"] == seed_user.id
