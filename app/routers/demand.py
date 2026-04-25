"""
Demand Prediction Router — exposes AI demand forecasts for stations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.demand_service import predict_demand, get_busiest_hours
from app.utils.response import success_response

router = APIRouter()


@router.get("/predict/{station_id}")
async def get_demand_prediction(
    station_id: UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get 24-hour demand forecast for a station.
    Returns predicted booking load per hour using weighted moving average of last 3 days.
    """
    predictions = await predict_demand(db, str(station_id))
    peak_hours = await get_busiest_hours(predictions, top_n=3)

    return success_response(
        data={
            "station_id": str(station_id),
            "forecast": predictions,
            "peak_hours": peak_hours,
        },
        message="Demand forecast generated."
    )
