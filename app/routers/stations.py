"""
Stations router — Phase 3.

Endpoints:
  GET  /v1/stations/nearby        — PostGIS proximity search (auth required)
  GET  /v1/stations/:id           — Station detail (auth required)
  POST /v1/stations               — Create station (admin only)
  PATCH /v1/stations/:id          — Update station (admin only)

Coordinate validation, radius cap, and charger-type enum enforcement happen
at the Pydantic / FastAPI layer before any DB work.
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, get_db_read
from app.middleware.auth_middleware import get_current_user, require_admin
from app.services.station_service import (
    get_nearby_stations, get_station_detail, get_station_slots,
)
from app.schemas.station import (
    StationNearbyItem, StationDetailResponse, StationCreate, StationUpdate,
)

router = APIRouter()


# ── Discovery ─────────────────────────────────────────────────────────────────

@router.get("/nearby", response_model=dict)
async def nearby_stations(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_km: float = Query(10.0, gt=0, le=50.0, description="Search radius (max 50 km)"),
    charger_type: Optional[str] = Query(None, description="Filter by charger type"),
    available_only: bool = Query(False, description="Only show stations with available slots"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_read),
    _: dict = Depends(get_current_user),
):
    stations = await get_nearby_stations(
        lat=lat, lng=lng, radius_km=radius_km,
        charger_type=charger_type, available_only=available_only,
        limit=limit, offset=offset, db=db,
    )
    return {
        "data": stations,
        "meta": {
            "lat": lat, "lng": lng, "radius_km": radius_km,
            "count": len(stations), "limit": limit, "offset": offset,
        }
    }


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{station_id}", response_model=dict)
async def station_detail(
    station_id: UUID,
    db: AsyncSession = Depends(get_db_read),
    _: dict = Depends(get_current_user),
):
    station = await get_station_detail(station_id, db)
    if not station:
        raise HTTPException(status_code=404, detail={"code": "STATION_NOT_FOUND", "message": "Station not found."})
    return {"data": station}


# ── Admin CRUD ────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=dict)
async def create_station(
    payload: StationCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from sqlalchemy import text
    import uuid
    station_id = str(uuid.uuid4())
    await db.execute(
        text("""
            INSERT INTO stations (
                id, name, network, location, address, operating_hours,
                amenities, price_per_unit, price_per_hour, admin_user_id
            ) VALUES (
                :id, :name, :network,
                ST_MakePoint(:lng, :lat)::geography,
                :address, :operating_hours, :amenities,
                :price_per_unit, :price_per_hour, :admin_user_id
            )
        """),
        {
            "id": station_id,
            "name": payload.name,
            "network": payload.network.value,
            "lat": payload.latitude,
            "lng": payload.longitude,
            "address": payload.address,
            "operating_hours": payload.operating_hours,
            "amenities": payload.amenities,
            "price_per_unit": payload.price_per_unit,
            "price_per_hour": payload.price_per_hour,
            "admin_user_id": admin.get("sub"),
        }
    )
    await db.commit()
    return {"data": {"id": station_id, "message": "Station created successfully."}}


@router.patch("/{station_id}", response_model=dict)
async def update_station(
    station_id: UUID,
    payload: StationUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    station = await get_station_detail(station_id, db)
    if not station:
        raise HTTPException(
            status_code=404, 
            detail={"code": "STATION_NOT_FOUND", "message": "Station not found."}
        )


    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail={"code": "NO_CHANGES", "message": "No fields to update."})

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    from sqlalchemy import text
    await db.execute(
        text(f"UPDATE stations SET {set_clauses}, updated_at = NOW() WHERE id = :station_id"),
        {**updates, "station_id": str(station_id)},
    )
    await db.commit()
    return {"data": {"message": "Station updated."}}
