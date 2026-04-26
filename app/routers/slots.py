"""
Slots router — Phase 3.

Endpoints:
  GET  /v1/stations/:station_id/slots   — List slots for a station (auth required)
  GET  /v1/slots/:slot_id              — Slot detail (auth required)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, get_db_read
from app.middleware.auth_middleware import get_current_user
from app.services.station_service import get_station_slots

router = APIRouter()


@router.get("/stations/{station_id}", response_model=dict)
async def list_station_slots(
    station_id: UUID,
    db: AsyncSession = Depends(get_db_read),
    _: dict = Depends(get_current_user),
):
    slots = await get_station_slots(station_id, db)
    return {"data": slots, "meta": {"station_id": str(station_id), "count": len(slots)}}


@router.get("/{slot_id}", response_model=dict)
async def get_slot_detail(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db_read),
    _: dict = Depends(get_current_user),
):
    result = await db.execute(
        text("""
            SELECT
                s.id::text, s.station_id::text, s.slot_number,
                s.charger_type, s.power_kw, s.status,
                s.fault_code, s.locked_until, s.created_at, s.updated_at,
                st.name AS station_name, st.network AS station_network
            FROM slots s
            JOIN stations st ON st.id = s.station_id
            WHERE s.id = :slot_id
        """),
        {"slot_id": str(slot_id)},
    )
    slot = result.mappings().first()
    if not slot:
        raise HTTPException(status_code=404, detail={"code": "SLOT_NOT_FOUND", "message": "Slot not found."})
    return {"data": dict(slot)}
