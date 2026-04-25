from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.booking import BookingCreateRequest, BookingInitResponse, BookingDetailResponse
from app.services.booking_service import create_booking
from app.config import settings

router = APIRouter()

@router.post("", response_model=dict)
async def request_booking(
    body: BookingCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        response = await create_booking(
            user_id=user["sub"],
            slot_id=str(body.slot_id),
            scheduled_start=body.scheduled_start,
            scheduled_end=body.scheduled_end,
            idempotency_key=idempotency_key,
            db=db,
        )
        return {"data": response}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "Failed to create booking."})

@router.get("", response_model=dict)
async def list_user_bookings(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT
            id::text, user_id::text, slot_id::text, station_id::text,
            status, scheduled_start, scheduled_end, actual_start,
            actual_end, amount, energy_consumed_kwh, created_at, updated_at
        FROM bookings
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """), {"user_id": user["sub"]})
    
    bookings = [dict(row) for row in result.mappings()]
    return {"data": bookings}

@router.delete("/{booking_id}", response_model=dict)
async def cancel_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # This invokes a simpler cancellation flow.
    # We first verify ownership and status.
    async with db.begin():
        result = await db.execute(text("""
            SELECT id, status FROM bookings WHERE id = :booking_id AND user_id = :user_id FOR UPDATE
        """), {"booking_id": str(booking_id), "user_id": user["sub"]})
        booking = result.mappings().first()

        if not booking:
            raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found."})
        
        if booking["status"] in ("ACTIVE", "COMPLETED", "CANCELLED_BY_USER", "CANCELLED_BY_ADMIN"):
             raise HTTPException(status_code=409, detail={"code": "BOOKING_NOT_CANCELLABLE", "message": f"Cannot cancel booking in status {booking['status']}"})

        await db.execute(text("""
            UPDATE bookings SET status = 'CANCELLED_BY_USER', updated_at = NOW() WHERE id = :booking_id
        """), {"booking_id": str(booking_id)})
        
    return {"data": {"status": "CANCELLED_BY_USER"}}

