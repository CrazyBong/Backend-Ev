from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

class ReviewCreateRequest(BaseModel):
    station_id: UUID
    booking_id: UUID | None = None
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1024)

class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    station_id: UUID
    booking_id: UUID | None = None
    rating: int
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
