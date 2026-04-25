"""
AI-based Demand Prediction Service.
Uses a weighted moving average over historical booking data (per hour-of-day)
to predict slot demand for the next 24 hours for a given station.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

WEIGHTS = [0.5, 0.3, 0.2]  # Most recent day gets highest weight


async def predict_demand(db, station_id: str) -> list[dict]:
    """
    Returns a 24-element list, one entry per hour (0-23), with:
      - hour: int
      - predicted_bookings: float (weighted avg across last 3 days)
      - load_percent: float (0-100, relative to peak hour)
    """
    result = await db.execute(text("""
        SELECT
            EXTRACT(HOUR FROM created_at AT TIME ZONE 'Asia/Kolkata') AS hour,
            DATE_TRUNC('day', created_at AT TIME ZONE 'Asia/Kolkata') AS day,
            COUNT(*) AS booking_count
        FROM bookings
        WHERE station_id = :station_id
          AND created_at >= NOW() - INTERVAL '3 days'
          AND status NOT IN ('CANCELLED_BY_USER', 'CANCELLED_BY_ADMIN', 'NO_SHOW')
        GROUP BY 1, 2
        ORDER BY 2 DESC, 1 ASC
    """), {"station_id": station_id})

    rows = result.mappings().all()

    # Organise data: { day_offset_0_1_2: { hour: count } }
    days_data: list[dict] = [{} for _ in range(3)]
    unique_days = sorted(set(str(r["day"]) for r in rows), reverse=True)[:3]
    day_index = {d: i for i, d in enumerate(unique_days)}

    for row in rows:
        day_key = str(row["day"])
        if day_key in day_index:
            idx = day_index[day_key]
            days_data[idx][int(row["hour"])] = int(row["booking_count"])

    # Compute weighted averages
    predictions = []
    for hour in range(24):
        weighted_sum = 0.0
        total_weight = 0.0
        for i, w in enumerate(WEIGHTS):
            if i < len(unique_days):
                count = days_data[i].get(hour, 0)
                weighted_sum += count * w
                total_weight += w
        predicted = weighted_sum / total_weight if total_weight > 0 else 0.0
        predictions.append({"hour": hour, "predicted_bookings": round(predicted, 2)})

    # Calculate load_percent (relative to peak)
    peak = max((p["predicted_bookings"] for p in predictions), default=1.0) or 1.0
    for p in predictions:
        p["load_percent"] = round((p["predicted_bookings"] / peak) * 100, 1)

    return predictions


async def get_busiest_hours(predictions: list[dict], top_n: int = 3) -> list[int]:
    """Returns the top N peak hours sorted by predicted load."""
    sorted_hours = sorted(predictions, key=lambda p: p["predicted_bookings"], reverse=True)
    return [h["hour"] for h in sorted_hours[:top_n]]
