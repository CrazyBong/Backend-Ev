"""
Demand Prediction Router — Phase 11 upgrade.

Endpoints:
  GET  /v1/demand/predict/{station_id}  — 24-hour forecast (RF or WMA)
  GET  /v1/demand/pricing/{station_id}  — Current surge multiplier + price
  POST /v1/demand/train/{station_id}    — Trigger model retrain (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.services.demand_service import predict_demand, get_busiest_hours
from app.services.pricing_service import calculate_surge_pricing
from app.ml.training import train_station_model
from app.utils.response import success_response

router = APIRouter()


@router.get("/predict/{station_id}", summary="24-hour demand forecast (ML or WMA)")
async def get_demand_prediction(
    station_id: UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a 24-hour hourly demand forecast for a station.
    - Uses Random Forest if a trained model exists on disk.
    - Falls back to Weighted Moving Average (3-day history) otherwise.
    - `model_type` field in the response tells you which engine ran.
    """
    predictions, model_type = await predict_demand(db, str(station_id))
    peak_hours = await get_busiest_hours(predictions, top_n=3)

    return success_response(
        data={
            "station_id": str(station_id),
            "forecast": predictions,
            "peak_hours": peak_hours,
            "model_type": model_type,
        },
        message="Demand forecast generated.",
    )


@router.get("/pricing/{station_id}", summary="Current surge pricing for a station")
async def get_surge_pricing(
    station_id: UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculates the current surge multiplier and effective price for immediate booking.

    Rules (auditable, not a black box):
    - load >= 80% → +50% surge
    - load >= 60% → +25% surge
    - load <= 20% → -10% off-peak discount
    - Weekend      → additional +15%
    - Hard cap: 3× base price, floor: 0.5× base price
    """
    from sqlalchemy import text
    # Fetch station's base price
    result = await db.execute(
        text("SELECT price_per_unit, price_per_hour FROM stations WHERE id = :sid AND is_active = true"),
        {"sid": str(station_id)},
    )
    station = result.mappings().first()
    if not station:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found.")

    unit_p = station.get("price_per_unit")
    hour_p = station.get("price_per_hour")
    base_price = float(unit_p if unit_p is not None else (hour_p if hour_p is not None else 0))
    if base_price == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Station has no base price configured.")

    predictions, _ = await predict_demand(db, str(station_id))
    pricing = calculate_surge_pricing(base_price, predictions)

    return success_response(
        data={"station_id": str(station_id), **pricing},
        message="Surge pricing calculated.",
    )


@router.post(
    "/train/{station_id}",
    summary="Trigger RF model training for a station (admin only)",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_training(
    station_id: UUID,
    user: dict = Depends(require_role("super_admin", "station_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Trains (or retrains) the Random Forest demand model for a station.

    - Requires ≥ 50 complete hourly booking data-points.
    - Returns `status: "skipped"` with a friendly reason if insufficient data.
    - Safe to call multiple times — re-training overwrites the previous model.
    """
    training_result = await train_station_model(db, str(station_id))
    return success_response(
        data={"station_id": str(station_id), **training_result},
        message="Training job complete.",
    )
