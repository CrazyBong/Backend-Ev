from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from app.models.station import ChargingNetwork
from app.models.slot import ChargerType, SlotStatus

class StationBase(BaseModel):
    name: str
    network: ChargingNetwork
    address: Dict[str, Any]
    operating_hours: Dict[str, Any]
    amenities: List[str] = []
    price_per_unit: Optional[Decimal] = None
    price_per_hour: Optional[Decimal] = None

class StationCreate(StationBase):
    latitude: float
    longitude: float

class StationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    operating_hours: Optional[Dict[str, Any]] = None
    amenities: Optional[List[str]] = None
    price_per_unit: Optional[Decimal] = None
    price_per_hour: Optional[Decimal] = None
    is_active: Optional[bool] = None

class StationResponse(StationBase):
    id: UUID
    is_active: bool
    total_slots: int
    available_slots: int
    avg_rating: Decimal
    total_reviews: int
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationNearbyItem(BaseModel):
    """Returned by the nearby search — includes lat/lng from PostGIS and distance."""
    id: str
    name: str
    network: str
    lat: float
    lng: float
    address: Dict[str, Any]
    available_slots: int
    total_slots: int
    avg_rating: Optional[Decimal] = None
    total_reviews: int
    price_per_unit: Optional[Decimal] = None
    price_per_hour: Optional[Decimal] = None
    amenities: Optional[List[str]] = None
    is_active: bool
    distance_km: float
    charger_types: Optional[List[Optional[str]]] = None

    model_config = ConfigDict(from_attributes=True)


class StationDetailResponse(StationNearbyItem):
    """Full station detail — superset of NearbyItem."""
    operating_hours: Dict[str, Any]
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SlotBase(BaseModel):
    slot_number: int
    charger_type: ChargerType
    power_kw: Decimal

class SlotResponse(SlotBase):
    id: UUID
    station_id: UUID
    status: SlotStatus
    fault_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
