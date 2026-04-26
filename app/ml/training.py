"""
Async training pipeline for the DemandForecaster.

Pulls all confirmed booking data for a station from the DB,
extracts features, and trains (or retrains) the RandomForest model.
Called by:
  - POST /v1/demand/train/{station_id}  (manual, admin-only)
  - Scheduler weekly retraining job     (automatic)
"""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_engineering import extract_features, FEATURE_COLS, TARGET_COL
from app.ml.model import DemandForecaster

logger = logging.getLogger(__name__)

# Completed / active bookings only — no cancelled/no-show noise
_VALID_STATUSES = ("COMPLETED", "ACTIVE", "CONFIRMED")


async def fetch_training_data(db: AsyncSession, station_id: str) -> list[dict]:
    """Pull all qualifying historical bookings for a station."""
    result = await db.execute(text("""
        SELECT
            DATE_TRUNC('hour', scheduled_start AT TIME ZONE 'UTC') AS scheduled_start,
            COUNT(*) AS booking_count
        FROM bookings
        WHERE station_id = :station_id
          AND status IN ('COMPLETED', 'ACTIVE', 'CONFIRMED')
        GROUP BY 1
        ORDER BY 1 ASC
    """), {"station_id": station_id})
    return [dict(r) for r in result.mappings().all()]


async def train_station_model(db: AsyncSession, station_id: str) -> dict:
    """
    Train (or retrain) the RandomForest model for a station.

    Returns a status dict that is passed directly to the API response.
    """
    rows = await fetch_training_data(db, station_id)
    n_rows = len(rows)

    forecaster = DemandForecaster(station_id)

    if not forecaster.has_enough_data(n_rows):
        logger.info(
            "Insufficient training data — skipping RF training, WMA remains active",
            extra={"station_id": station_id, "available_rows": n_rows, "required": 50},
        )
        return {
            "status": "skipped",
            "reason": f"Only {n_rows} hourly data-points available (minimum 50 required). "
                      "WMA fallback is active. Re-trigger once more bookings accumulate.",
            "available_samples": n_rows,
        }

    df = extract_features(rows)
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    forecaster.train(X, y)

    return {
        "status": "trained",
        "model": "RandomForestRegressor",
        "training_samples": n_rows,
        "station_id": station_id,
    }
