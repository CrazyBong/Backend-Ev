from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class BookingCreateRequest(BaseModel):
    slot_id: UUID
    scheduled_start: datetime
    scheduled_end: datetime

    model_config = ConfigDict(from_attributes=True)

class BookingDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    slot_id: UUID
    station_id: UUID
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    amount: float
    energy_consumed_kwh: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BookingInitResponse(BaseModel):
    booking_id: UUID
    razorpay_order_id: str
    amount: float
    lock_expires_at: datetime

    model_config = ConfigDict(from_attributes=True)
