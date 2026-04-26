"""
Dynamic Pricing Service — surge multiplier calculation.

Design principle: Rules-based, NOT a black box.
Every pricing decision is fully auditable and explainable.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

# ── Surge thresholds ──────────────────────────────────────────────────────────
_SURGE_HIGH_THRESHOLD = 80.0     # load_percent >= 80 → HIGH demand
_SURGE_MEDIUM_THRESHOLD = 60.0   # load_percent >= 60 → MEDIUM demand
_DISCOUNT_THRESHOLD = 20.0       # load_percent <= 20 → off-peak discount
_MAX_SURGE_MULTIPLIER = 3.0      # Hard cap — never charge more than 3× base

# ── Multiplier components ─────────────────────────────────────────────────────
_HIGH_DEMAND_PREMIUM = 0.50
_MEDIUM_DEMAND_PREMIUM = 0.25
_WEEKEND_PREMIUM = 0.15
_OFF_PEAK_DISCOUNT = -0.10


def _current_load_percent(predictions: list[dict]) -> float:
    """Return the load_percent for the current IST hour."""
    now_ist = datetime.now(timezone.utc)
    current_hour = (now_ist.hour + 5) % 24  # rough IST shift
    for p in predictions:
        if p["hour"] == current_hour:
            return float(p["load_percent"])
    return 0.0


def _is_weekend_ist() -> bool:
    now_ist = pd.Timestamp.now('UTC') + pd.Timedelta(hours=5, minutes=30)
    return now_ist.dayofweek >= 5


def calculate_surge_pricing(
    base_price: float,
    predictions: list[dict],
) -> dict:
    """
    Calculate the current surge price for a station.

    Args:
        base_price: The station's base price_per_unit (from DB).
        predictions: 24-element forecast list from demand_service.predict_demand().

    Returns:
        dict with keys: base_price, surge_price, surge_multiplier, reason, valid_until_hour
    """
    load_percent = _current_load_percent(predictions)
    is_weekend = _is_weekend_ist()

    multiplier = 1.0
    reasons: list[str] = []

    if load_percent >= _SURGE_HIGH_THRESHOLD:
        multiplier += _HIGH_DEMAND_PREMIUM
        reasons.append(f"High demand ({load_percent:.0f}% load, +50%)")
    elif load_percent >= _SURGE_MEDIUM_THRESHOLD:
        multiplier += _MEDIUM_DEMAND_PREMIUM
        reasons.append(f"Medium demand ({load_percent:.0f}% load, +25%)")
    elif load_percent <= _DISCOUNT_THRESHOLD:
        multiplier += _OFF_PEAK_DISCOUNT
        reasons.append(f"Off-peak discount ({load_percent:.0f}% load, -10%)")

    if is_weekend:
        multiplier += _WEEKEND_PREMIUM
        reasons.append("Weekend premium (+15%)")

    # Hard cap
    multiplier = min(multiplier, _MAX_SURGE_MULTIPLIER)
    multiplier = max(multiplier, 0.5)  # Never less than 50% of base (floor)

    surge_price = float(
        (Decimal(str(base_price)) * Decimal(str(round(multiplier, 4))))
        .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    reason = " | ".join(reasons) if reasons else "Standard pricing"

    # Valid for 1 hour
    now_ist = pd.Timestamp.now('UTC') + pd.Timedelta(hours=5, minutes=30)
    valid_until_hour = (now_ist.hour + 1) % 24

    logger.info(
        "Surge pricing calculated",
        extra={
            "load_percent": load_percent,
            "multiplier": round(multiplier, 4),
            "surge_price": surge_price,
        },
    )

    return {
        "base_price": round(float(base_price), 2),
        "surge_price": surge_price,
        "surge_multiplier": round(multiplier, 4),
        "reason": reason,
        "valid_until_hour": valid_until_hour,
    }
