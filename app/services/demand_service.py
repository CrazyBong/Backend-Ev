"""
AI-based Demand Prediction Service.

Phase 11 upgrade: tries RandomForest first; falls back to WMA if model
hasn't been trained yet (cold start) or model file is missing.
"""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WEIGHTS = [0.5, 0.3, 0.2]  # WMA: most recent day gets highest weight


# ── WMA Implementation (unchanged, Day-0 production algorithm) ─────────────

async def _wma_predict(db: AsyncSession, station_id: str) -> list[dict]:
    """Weighted Moving Average over last 3 days of booking history."""
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

    days_data: list[dict] = [{} for _ in range(3)]
    unique_days = sorted(set(str(r["day"]) for r in rows), reverse=True)[:3]
    day_index = {d: i for i, d in enumerate(unique_days)}

    for row in rows:
        day_key = str(row["day"])
        if day_key in day_index:
            idx = day_index[day_key]
            days_data[idx][int(row["hour"])] = int(row["booking_count"])

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

    peak = max((p["predicted_bookings"] for p in predictions), default=1.0)
    if peak <= 0:
        peak = 1.0
    for p in predictions:
        p["load_percent"] = round((p["predicted_bookings"] / peak) * 100, 1)

    return predictions


# ── Unified predict_demand (RF → WMA fallback) ─────────────────────────────

async def predict_demand(
    db: AsyncSession,
    station_id: str,
) -> tuple[list[dict], str]:
    """
    Returns (24-element list, model_type_str).

    model_type_str is 'random_forest' or 'weighted_average'
    so the API response can tell clients which engine ran.
    """
    from app.ml.model import DemandForecaster  # lazy, avoids import at module load

    forecaster = DemandForecaster(station_id)
    if forecaster.load():
        try:
            predictions = forecaster.predict_24h()
            # load_percent not computed by RF — compute it now
            peak = max((p["predicted_bookings"] for p in predictions), default=1.0)
            if peak <= 0:
                peak = 1.0
            for p in predictions:
                p["load_percent"] = round((p["predicted_bookings"] / peak) * 100, 1)
            logger.info("RF prediction used", extra={"station_id": station_id})
            return predictions, "random_forest"
        except Exception as exc:
            logger.warning("RF predict failed, falling back to WMA",
                           extra={"station_id": station_id, "error": str(exc)})

    predictions = await _wma_predict(db, station_id)
    return predictions, "weighted_average"


async def get_busiest_hours(predictions: list[dict], top_n: int = 3) -> list[int]:
    """Returns the top N peak hours sorted by predicted load."""
    sorted_hours = sorted(predictions, key=lambda p: p["predicted_bookings"], reverse=True)
    return [h["hour"] for h in sorted_hours[:top_n]]
