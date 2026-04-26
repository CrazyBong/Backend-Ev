import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.redis import get_redis
from app.schemas.route import RoutePlanRequest, RoutePlanResponse
from app.services.route_service import plan_ev_route, RouteNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/plan", response_model=RoutePlanResponse)
async def plan_route(
    body: RoutePlanRequest,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Plan EV route fetching charging stops where vehicle battery will drop below safe range.
    Uses Google Maps Directions.
    """
    try:
        result = await plan_ev_route(
            origin_lat=body.origin_lat,
            origin_lng=body.origin_lng,
            dest_lat=body.dest_lat,
            dest_lng=body.dest_lng,
            current_battery_percent=body.current_battery_percent,
            vehicle_range_km=body.vehicle_range_km,
            db=db,
            redis=redis
        )
        return result
    except RouteNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "ROUTE_NOT_FOUND", "message": str(e)})
    except Exception as e:
        logger.error(f"Route planning failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "ROUTE_ERROR", "message": "Failed to plan route"})
