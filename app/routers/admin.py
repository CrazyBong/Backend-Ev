"""
Admin API Router — station admin operations on slots.
Only users with role 'station_admin' or 'admin' can access these endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from pydantic import BaseModel
from typing import Literal

from app.db.database import get_db
from app.db.redis import get_redis
from app.middleware.auth_middleware import get_current_user
from app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter()


class SlotStatusUpdate(BaseModel):
    status: Literal["AVAILABLE", "OFFLINE"]
    reason: str | None = None


async def _verify_station_access(station_id: UUID, user: dict, db: AsyncSession):
    """
    FAANG-level Authorization: Check if user has permission for THIS specific station.
    - super_admin: Allow all.
    - station_admin: Must exist in station_managers for this station.
    - others: Forbidden.
    """
    role = user.get("role")
    
    if role == "super_admin":
        return
        
    if role == "station_admin" or role == "admin":
        # Check ownership table
        res = await db.execute(text("""
            SELECT 1 FROM station_managers 
            WHERE user_id = :user_id AND station_id = :station_id
        """), {"user_id": user["sub"], "station_id": str(station_id)})
        
        if res.scalar():
            return

    raise HTTPException(
        status_code=403,
        detail=error_response("FORBIDDEN", "You do not have permission to manage this station.")
    )


@router.patch("/stations/{station_id}/slots/{slot_id}")
async def admin_update_slot_status(
    station_id: UUID,
    slot_id: UUID,
    body: SlotStatusUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Admin: Update a slot status.
    If marking as OFFLINE, cancel all active/pending bookings on that slot
    and send in-app notifications to affected users.
    """
    # Enforce granular ownership check
    await _verify_station_access(station_id, user, db)

    # Verify slot belongs to station
    slot = await db.execute(text("""
        SELECT s.id, s.status, s.station_id
        FROM slots s
        WHERE s.id = :slot_id AND s.station_id = :station_id
    """), {"slot_id": str(slot_id), "station_id": str(station_id)})
    slot_row = slot.mappings().first()
    if not slot_row:
        raise HTTPException(
            status_code=404,
            detail=error_response("NOT_FOUND", "Slot not found for this station.")
        )

    old_status = slot_row["status"]
    new_status = body.status

    # Update slot status
    await db.execute(text("""
        UPDATE slots SET status = :status, updated_at = NOW()
        WHERE id = :slot_id
    """), {"status": new_status, "slot_id": str(slot_id)})

    # If going offline, cascade: cancel active bookings + notify users
    affected_user_ids = []
    if new_status == "OFFLINE" and old_status not in ("OFFLINE",):
        bookings_res = await db.execute(text("""
            UPDATE bookings
            SET status = 'CANCELLED_BY_ADMIN', updated_at = NOW()
            WHERE slot_id = :slot_id
              AND status IN ('CONFIRMED', 'PENDING_PAYMENT', 'ACTIVE')
            RETURNING user_id, id
        """), {"slot_id": str(slot_id)})
        cancelled = bookings_res.mappings().all()
        affected_user_ids = [str(r["user_id"]) for r in cancelled]

    await db.commit()

    # Release lock after commit succeeds
    if new_status == "OFFLINE" and old_status not in ("OFFLINE",):
        try:
            await redis.delete(f"slot_lock:{slot_id}")
        except Exception as e:
            logger.warning(f"Could not release Redis lock for slot {slot_id}: {e}")

    # Non-blocking notification for affected users
    if affected_user_ids:
        try:
            from app.services.notification_service import store_notification
            for uid in affected_user_ids:
                await store_notification(
                    db=db,
                    user_id=uid,
                    notif_type="BOOKING_CANCELLED",
                    title="Booking Cancelled",
                    body=f"Your booking was cancelled because slot went offline. Reason: {body.reason or 'Maintenance'}.",
                )
        except Exception as e:
            logger.error(f"Failed to send cancellation notifications: {e}")

    return success_response(
        data={
            "slot_id": str(slot_id),
            "old_status": old_status,
            "new_status": new_status,
            "affected_bookings": len(affected_user_ids),
        },
        message=f"Slot status updated to {new_status}."
    )


@router.get("/stations/{station_id}/bookings")
async def admin_get_station_bookings(
    station_id: UUID,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: View all bookings for a station with optional status filter."""
    # Enforce granular ownership check
    await _verify_station_access(station_id, user, db)

    query = """
        SELECT b.id, b.user_id, b.slot_id, b.status, b.scheduled_start, b.scheduled_end,
               b.amount, b.created_at, u.phone
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        WHERE b.station_id = :station_id
    """
    params: dict = {"station_id": str(station_id), "limit": limit, "offset": offset}

    if status:
        query += " AND b.status = :status"
        params["status"] = status

    query += " ORDER BY b.created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    bookings = [dict(r) for r in result.mappings()]

    return success_response(
        data=bookings,
        meta={"limit": limit, "offset": offset, "count": len(bookings)},
    )
