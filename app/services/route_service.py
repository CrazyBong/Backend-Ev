import json
import logging
import httpx
from geoalchemy2 import WKTElement
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

class RouteNotFoundError(Exception):
    pass


async def _find_charging_stops_along_route(route: dict, current_range_km: float, vehicle_range_km: float, db) -> list:
    """Finds stations near the point where range would fail."""
    stops = []
    accumulated_distance = 0.0

    steps = []
    for leg in route.get("legs", []):
        steps.extend(leg.get("steps", []))

    for step in steps:
        step_dist = step["distance"]["value"] / 1000.0
        
        while accumulated_distance + step_dist >= current_range_km:
            # Range fails in this interval. Look for a station around the start of this step
            lat = step["start_location"]["lat"]
            lng = step["start_location"]["lng"]

            # Query PostGIS for closest active station within 20km
            result = await db.execute(text("""
                SELECT id, name,
                       ST_Y(location::geometry) AS st_lat,
                       ST_X(location::geometry) AS st_lng,
                       ST_Distance(location, ST_GeomFromText(:point, 4326)::geography) / 1000 AS dist_km
                FROM stations
                WHERE is_active = TRUE
                  AND ST_DWithin(location, ST_GeomFromText(:point, 4326)::geography, 20000)
                ORDER BY dist_km ASC
                LIMIT 1
            """), {"point": f"POINT({lng} {lat})"})

            station = result.mappings().first()

            if station:
                stops.append({
                    "station_id": str(station["id"]),
                    "station_name": station["name"],
                    "location": {"lat": float(station["st_lat"]), "lng": float(station["st_lng"])},
                    "distance_from_origin_km": accumulated_distance,
                })
                current_range_km = accumulated_distance + (vehicle_range_km * 0.9)
            else:
                raise RouteNotFoundError("No reachable charging stations available to complete this route.")

        accumulated_distance += step_dist

    return stops


async def plan_ev_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    current_battery_percent: float,
    vehicle_range_km: float,
    db, redis,
) -> dict:
    # 1. Check cache
    cache_key = f"route:{origin_lat:.4f}:{origin_lng:.4f}:{dest_lat:.4f}:{dest_lng:.4f}:{current_battery_percent:.1f}:{vehicle_range_km:.1f}"
    cached = await redis.get(cache_key)
    if cached:
        # Cache hit
        return json.loads(cached)

    # 2. Get route from Google Maps
    try:
        async with httpx.AsyncClient() as client:
            directions_res = await client.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin": f"{origin_lat},{origin_lng}",
                    "destination": f"{dest_lat},{dest_lng}",
                    "mode": "driving",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                },
                timeout=10.0,
            )
            directions_res.raise_for_status()
    except httpx.RequestError as e:
        logger.error(f"Google Maps API request failed: {e}")
        raise RouteNotFoundError("Failed to fetch directions from routing service.")

    route_data = directions_res.json()
    if not route_data.get("routes"):
        raise RouteNotFoundError("No route found between origin and destination.")

    route = route_data["routes"][0]
    total_distance_km = sum(leg["distance"]["value"] for leg in route.get("legs", [])) / 1000.0

    # 3. Assess Range
    current_range_km = (current_battery_percent / 100.0) * vehicle_range_km * 0.9  # 10% safety buffer

    if current_range_km >= total_distance_km:
        result = {
            "route": route_data["routes"][0],
            "charging_stops": [],
            "total_distance_km": total_distance_km,
            "range_sufficient": True,
        }
    else:
        # 4. Compute stops
        charging_stops = await _find_charging_stops_along_route(
            route_data["routes"][0], current_range_km, vehicle_range_km, db
        )

        result = {
            "route": route_data["routes"][0],
            "charging_stops": charging_stops,
            "total_distance_km": total_distance_km,
            "range_sufficient": False,
        }

    # 5. Cache result
    await redis.setex(cache_key, 300, json.dumps(result, default=str))
    
    return result
