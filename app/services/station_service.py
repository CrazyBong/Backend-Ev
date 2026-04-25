"""
Phase 3 — Station & Slot geospatial service.

Design decisions:
  - All radius math is pushed to the DB (PostGIS ST_DWithin / ST_Distance) —
    this is the Architecture Principle P5 from the HLD.
  - Results are cached in Redis with a 10-second TTL for eventual consistency
    during high-traffic discovery requests.
  - Charger-type and availability filters are safely injected via string
    replacement before parameterisation (parameters cannot be used for
    identifier/keyword injection; the filter is a SQL fragment, not a value).
  - max_radius capped at 50 km per business rules.
"""
import json
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis


# ──────────────────────────────────────────────────────────────────────────────
# Nearby stations discovery
# ──────────────────────────────────────────────────────────────────────────────

async def get_nearby_stations(
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    charger_type: Optional[str] = None,
    available_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = None,  # Will be validated below
) -> list:
    if db is None:
        raise ValueError("Database session is required")

    # Business rule: absolute cap at 50km
    radius_km = min(radius_km, 50.0)

    redis = await get_redis()

    # Issue: Cache key must include pagination params to avoid stale results for different pages
    cache_key = f"nearby:{lat:.4f}:{lng:.4f}:{radius_km}:{charger_type}:{available_only}:{limit}:{offset}"
    cached = await redis.get(cache_key)
    if cached:
        # Explicit decoding for Redis bytes
        val = cached.decode("utf-8") if isinstance(cached, bytes) else cached
        return json.loads(val)

    # Build optional SQL filter fragments
    charger_filter = (
        "AND EXISTS (SELECT 1 FROM slots WHERE station_id = s.id AND charger_type = :charger_type)"
        if charger_type else ""
    )
    availability_filter = "AND s.available_slots > 0" if available_only else ""

    raw_sql = f"""
        SELECT
            s.id::text,
            s.name,
            s.network,
            ST_Y(s.location::geometry)  AS lat,
            ST_X(s.location::geometry)  AS lng,
            s.address,
            s.available_slots,
            s.total_slots,
            s.avg_rating,
            s.total_reviews,
            s.price_per_unit,
            s.price_per_hour,
            s.amenities,
            s.is_active,
            ROUND(
                (ST_Distance(s.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000.0)::numeric, 
                2
            )::float AS distance_km,
            -- Issue: array_agg returns [NULL] if join finds no rows; use FILTER to return empty array
            COALESCE(array_agg(DISTINCT sl.charger_type) FILTER (WHERE sl.charger_type IS NOT NULL), '{{}}') AS charger_types

        FROM stations s
        LEFT JOIN slots sl ON sl.station_id = s.id
        WHERE
            s.is_active = TRUE
            AND ST_DWithin(
                s.location, 
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 
                CAST(:radius_km AS float) * 1000
            )
            {charger_filter}
            {availability_filter}
        GROUP BY s.id
        ORDER BY distance_km ASC
        LIMIT :limit OFFSET :offset
    """

    params = {
        "lat": lat,
        "lng": lng,
        "radius_km": radius_km,
        "limit": limit,
        "offset": offset,
    }
    if charger_type:
        params["charger_type"] = charger_type

    result = await db.execute(text(raw_sql), params)
    stations = [dict(row) for row in result.mappings()]

    await redis.setex(cache_key, 10, json.dumps(stations, default=str))
    return stations


# ──────────────────────────────────────────────────────────────────────────────
# Station detail
# ──────────────────────────────────────────────────────────────────────────────

async def get_station_detail(station_id: UUID, db: AsyncSession) -> Optional[dict]:
    result = await db.execute(
        text("""
            SELECT
                s.id::text, s.name, s.network, s.address, s.operating_hours,
                s.amenities, s.price_per_unit, s.price_per_hour,
                s.is_active, s.total_slots, s.available_slots,
                s.avg_rating, s.total_reviews, s.last_heartbeat,
                s.created_at, s.updated_at,
                ST_Y(s.location::geometry) AS lat,
                ST_X(s.location::geometry) AS lng
            FROM stations s
            WHERE s.id = :station_id
        """),
        {"station_id": str(station_id)},
    )
    row = result.mappings().first()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────────────────
# Slot listing for a station
# ──────────────────────────────────────────────────────────────────────────────

async def get_station_slots(station_id: UUID, db: AsyncSession) -> list:
    result = await db.execute(
        text("""
            SELECT
                id::text, station_id::text, slot_number, charger_type,
                power_kw, status, fault_code, locked_until,
                created_at, updated_at
            FROM slots
            WHERE station_id = :station_id
            ORDER BY slot_number ASC
        """),
        {"station_id": str(station_id)},
    )
    return [dict(row) for row in result.mappings()]
