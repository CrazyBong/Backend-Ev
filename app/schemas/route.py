from pydantic import BaseModel, Field
from typing import List, Any

class RoutePlanRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lng: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lng: float = Field(..., ge=-180, le=180)
    current_battery_percent: float = Field(..., ge=1, le=100)
    vehicle_range_km: float = Field(..., gt=0)

class ChargingStop(BaseModel):
    station_id: str
    station_name: str
    location: dict
    distance_from_origin_km: float

class RoutePlanResponse(BaseModel):
    route: Any
    charging_stops: List[ChargingStop] = []
    total_distance_km: float
    range_sufficient: bool
