import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config import settings
from app.db.database import get_db
from app.models.slot import Slot
from app.websockets.manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

IOT_API_KEY = settings.IOT_API_KEY.get_secret_value()

from typing import Literal

class HeartbeatPayload(BaseModel):
    slot_id: str
    status: Literal["AVAILABLE", "IN_USE", "OFFLINE", "FAULTED", "CHARGING"]
    current_draw_kw: float

import secrets

async def verify_iot_key(x_iot_key: str = Header(...)):
    if not secrets.compare_digest(x_iot_key, IOT_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid IoT API Key")

def map_iot_status(status: str) -> str:
    """Map IoT raw status to DB slot status."""
    st = status.upper()
    if st == "CHARGING":
        return "IN_USE"
    return st

@router.post("/heartbeat", dependencies=[Depends(verify_iot_key)])
async def iot_heartbeat(payload: HeartbeatPayload, db: AsyncSession = Depends(get_db)):
    # Validate slot exists FIRST
    try:
        slot_uuid = uuid.UUID(payload.slot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot_id format")

    slot = await db.get(Slot, slot_uuid)
    if not slot:
        raise HTTPException(status_code=404, detail=f"Slot {payload.slot_id} not found")
    
    # In a real app we might not block on OFFLINE if the heartbeat is telling us it's back online!
    # But as per the review, reject if inactive
    if hasattr(slot, "is_active") and not getattr(slot, "is_active", True):
        raise HTTPException(status_code=409, detail="Slot is offline")

    # Update DB
    new_status = map_iot_status(payload.status)

    slot.status = new_status
    await db.commit()

    # Broadcast via WebSocket
    message = {
        "event": "SLOT_STATUS_CHANGE",
        "slot_id": payload.slot_id,
        "status": slot.status,
        "current_draw_kw": payload.current_draw_kw,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_slot(payload.slot_id, message)

    logger.info(f"IoT Heartbeat processed for slot {payload.slot_id}. New status: {slot.status}")
    return {"ok": True, "slot_id": payload.slot_id, "new_status": slot.status}
