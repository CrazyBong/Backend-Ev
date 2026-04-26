"""
Feature Engineering for Demand Forecasting.

Converts raw booking rows (dicts with 'scheduled_start', 'booking_count')
into a pandas DataFrame with time-based features ready for model training
or inference.
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST_TZ = ZoneInfo("Asia/Kolkata")

def _to_ist(dt: datetime | str | pd.Timestamp) -> pd.Timestamp:
    """Convert an aware/naive UTC datetime to IST naive for feature extraction."""
    ts = pd.Timestamp(dt)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(IST_TZ).tz_localize(None)


def extract_features(rows: list[dict]) -> pd.DataFrame:
    """
    Build a feature DataFrame from historical booking aggregates.

    Args:
        rows: list of dicts with keys:
              - 'scheduled_start': datetime (UTC-aware or naive)
              - 'booking_count': int

    Returns:
        DataFrame with columns:
            hour, day_of_week, month, is_weekend, booking_count
    """
    records = []
    for row in rows:
        ts_ist = _to_ist(row["scheduled_start"])
        records.append({
            "hour": ts_ist.hour,
            "day_of_week": ts_ist.dayofweek,        # 0=Monday … 6=Sunday
            "month": ts_ist.month,
            "is_weekend": int(ts_ist.dayofweek >= 5),
            "booking_count": int(row["booking_count"]),
        })
    return pd.DataFrame(records)


def build_inference_grid() -> pd.DataFrame:
    """
    Build a 24-row DataFrame (hour 0-23) using current IST weekday/month,
    suitable for passing to model.predict() to get today's forecast.
    """
    now_ist = pd.Timestamp.now(IST_TZ)
    rows = []
    for hour in range(24):
        rows.append({
            "hour": hour,
            "day_of_week": now_ist.dayofweek,
            "month": now_ist.month,
            "is_weekend": int(now_ist.dayofweek >= 5),
        })
    return pd.DataFrame(rows)


FEATURE_COLS = ["hour", "day_of_week", "month", "is_weekend"]
TARGET_COL = "booking_count"
