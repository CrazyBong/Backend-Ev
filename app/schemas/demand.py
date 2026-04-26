"""
Pydantic response schemas for Phase 11 Demand & Pricing endpoints.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from uuid import UUID


class HourlyForecast(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (IST, 0-23)")
    predicted_bookings: float = Field(..., ge=0)
    load_percent: float = Field(..., ge=0, le=100)


class DemandForecastResponse(BaseModel):
    station_id: str
    forecast: list[HourlyForecast]
    peak_hours: list[int]
    model_type: str = Field(..., description='"random_forest" or "weighted_average"')


class SurgePricingResponse(BaseModel):
    station_id: str
    base_price: float
    surge_price: float
    surge_multiplier: float
    reason: str
    valid_until_hour: int


class TrainingStatusResponse(BaseModel):
    station_id: str
    status: str = Field(..., description='"trained" | "skipped"')
    reason: str | None = None
    training_samples: int | None = None
    model: str | None = None
    available_samples: int | None = None
