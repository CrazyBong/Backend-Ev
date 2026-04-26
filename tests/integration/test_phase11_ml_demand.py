"""
Phase 11 Integration Tests: ML Demand Forecasting & Dynamic Pricing

Edge cases covered:
  - Forecast returns exactly 24 hourly entries (shape validation)
  - model_type = 'weighted_average' on cold start (no model file)
  - Forecast has load_percent in [0, 100] for all hours
  - Peak hours list has <= 3 elements and is a subset of valid hours
  - Pricing endpoint returns base price when no bookings (no surge)
  - Pricing endpoint returns surge > base when load forced high
  - Pricing endpoint 404 on unknown station
  - Admin train endpoint returns 'skipped' when < 50 booking rows
  - Non-admin cannot call train endpoint (403)
  - Feature engineering produces correct columns (unit test)
  - Surge multiplier capped at 3.0 hard ceiling
"""
import pytest
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


# ── Helpers ─────────────────────────────────────────────────────────────────

class _MockUser:
    def __init__(self, uid, role):
        self.id = uid
        self.role = role

def _token(user_data: dict):
    from app.services.auth_service import create_access_token
    mock_user = _MockUser(user_data["user_id"], user_data["role"])
    return create_access_token(mock_user)


def _auth(user_data: dict):
    return {"Authorization": f"Bearer {_token(user_data)}"}


async def _seed_station(db_session, price: float = 10.0) -> str:
    sid = str(uuid4())
    await db_session.execute(text("""
        INSERT INTO stations (id, name, network, location, address, operating_hours, price_per_unit, is_active, total_slots, available_slots)
        VALUES (:id, 'ML Test Station', 'TATA_POWER',
                ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
                '{"city":"Bengaluru"}'::jsonb,
                '{"open":"00:00","close":"23:59"}'::jsonb,
                :price, true, 5, 5)
    """), {"id": sid, "price": price})
    await db_session.commit()
    return sid


async def _seed_user(db_session, role: str = "user") -> dict:
    uid = str(uuid4())
    phone = f"+917{uuid4().hex[:9]}"
    await db_session.execute(text("""
        INSERT INTO users (id, phone, role, is_active)
        VALUES (:id, :phone, :role, true)
    """), {"id": uid, "phone": phone, "role": role})
    await db_session.commit()
    return {"user_id": uid, "sub": uid, "role": role, "type": "access",
            "jti": str(uuid4()), "phone": phone}


# ══════════════════════════════════════════════════════════════════════════════
# Class A: Demand Forecast Endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestDemandForecast:

    async def test_returns_24_hourly_entries(self, client, db_session):
        """Forecast must always have exactly 24 entries (0-23)."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session)

        resp = await client.get(f"/v1/demand/predict/{sid}", headers=_auth(user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["forecast"]) == 24
        hours = [entry["hour"] for entry in data["forecast"]]
        assert hours == list(range(24))

    async def test_cold_start_uses_wma(self, client, db_session):
        """With no trained model file, model_type must be 'weighted_average'."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session)

        with patch("app.ml.model.DemandForecaster.model_exists", return_value=False):
            resp = await client.get(f"/v1/demand/predict/{sid}", headers=_auth(user))

        assert resp.status_code == 200
        assert resp.json()["data"]["model_type"] == "weighted_average"

    async def test_load_percent_bounded(self, client, db_session):
        """All load_percent values must be in [0, 100]."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session)

        resp = await client.get(f"/v1/demand/predict/{sid}", headers=_auth(user))
        assert resp.status_code == 200
        for entry in resp.json()["data"]["forecast"]:
            assert 0.0 <= entry["load_percent"] <= 100.0

    async def test_peak_hours_is_subset_of_valid_hours(self, client, db_session):
        """Peak hours must be valid (0-23) ints, max 3 returned."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session)

        resp = await client.get(f"/v1/demand/predict/{sid}", headers=_auth(user))
        assert resp.status_code == 200
        peak_hours = resp.json()["data"]["peak_hours"]
        assert len(peak_hours) <= 3
        for h in peak_hours:
            assert 0 <= h <= 23

    async def test_unauthenticated_returns_401(self, client, db_session):
        sid = await _seed_station(db_session)
        resp = await client.get(f"/v1/demand/predict/{sid}")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# Class B: Surge Pricing Endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestSurgePricing:

    async def test_base_price_returned_at_low_load(self, client, db_session):
        """Zero bookings → zero load → off-peak discount → surge_price <= base."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session, price=10.0)

        with patch("app.services.pricing_service._is_weekend_ist", return_value=False):
            resp = await client.get(f"/v1/demand/pricing/{sid}", headers=_auth(user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["base_price"] == 10.0
        assert data["surge_multiplier"] <= 1.0
        assert data["surge_price"] <= data["base_price"]

    async def test_surge_applied_at_high_load(self, client, db_session):
        """When load is forced to 90%, surge_multiplier must be > 1.0."""
        user = await _seed_user(db_session)
        sid = await _seed_station(db_session, price=10.0)

        high_load_predictions = [
            {"hour": h, "predicted_bookings": 9.0 if h == 14 else 0.0, "load_percent": 90.0 if h == 14 else 0.0}
            for h in range(24)
        ]
        with patch("app.routers.demand.predict_demand", return_value=(high_load_predictions, "weighted_average")), \
             patch("app.services.pricing_service._current_load_percent", return_value=90.0):
            resp = await client.get(f"/v1/demand/pricing/{sid}", headers=_auth(user))

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["surge_multiplier"] > 1.0
        assert data["surge_price"] > data["base_price"]

    async def test_unknown_station_returns_404(self, client, db_session):
        user = await _seed_user(db_session)
        resp = await client.get(f"/v1/demand/pricing/{uuid4()}", headers=_auth(user))
        assert resp.status_code == 404

    async def test_unauthenticated_returns_401(self, client, db_session):
        sid = await _seed_station(db_session)
        resp = await client.get(f"/v1/demand/pricing/{sid}")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# Class C: Model Training Endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestModelTraining:

    async def test_admin_can_trigger_training_skipped_on_cold_start(self, client, db_session):
        """Admin with no booking data → status='skipped' (< 50 rows)."""
        admin = await _seed_user(db_session, role="super_admin")
        sid = await _seed_station(db_session)

        resp = await client.post(f"/v1/demand/train/{sid}", headers=_auth(admin))
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["status"] == "skipped"
        assert "available_samples" in data

    async def test_non_admin_cannot_trigger_training(self, client, db_session):
        """Regular user must get 403 on the /train endpoint."""
        user = await _seed_user(db_session, role="user")
        sid = await _seed_station(db_session)

        resp = await client.post(f"/v1/demand/train/{sid}", headers=_auth(user))
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_trigger_training(self, client, db_session):
        sid = await _seed_station(db_session)
        resp = await client.post(f"/v1/demand/train/{sid}")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# Class D: Unit Tests — Feature Engineering (sync, no fixtures needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestFeatureEngineering:

    def test_extract_features_produces_correct_columns(self):
        from app.ml.feature_engineering import extract_features, FEATURE_COLS, TARGET_COL
        from datetime import datetime, timezone

        rows = [
            {"scheduled_start": datetime(2024, 4, 15, 14, 0, 0, tzinfo=timezone.utc), "booking_count": 5},
            {"scheduled_start": datetime(2024, 4, 15, 18, 0, 0, tzinfo=timezone.utc), "booking_count": 3},
        ]
        df = extract_features(rows)
        for col in FEATURE_COLS + [TARGET_COL]:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == 2

    def test_inference_grid_has_24_rows(self):
        from app.ml.feature_engineering import build_inference_grid
        grid = build_inference_grid()
        assert len(grid) == 24
        assert list(grid["hour"]) == list(range(24))


# ══════════════════════════════════════════════════════════════════════════════
# Class E: Unit Tests — Surge Pricing Rules (sync, no fixtures needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestSurgeMultiplierRules:

    def test_surge_multiplier_hard_cap(self):
        """Hard cap: multiplier must never exceed 3.0."""
        from app.services.pricing_service import calculate_surge_pricing
        predictions = [{"hour": h, "load_percent": 100.0, "predicted_bookings": 10.0} for h in range(24)]
        with patch("app.services.pricing_service._current_load_percent", return_value=100.0), \
             patch("app.services.pricing_service._is_weekend_ist", return_value=True):
            result = calculate_surge_pricing(base_price=100.0, predictions=predictions)
        assert result["surge_multiplier"] <= 3.0

    def test_off_peak_gives_discount(self):
        """load_percent <= 20 on weekday → multiplier < 1.0."""
        from app.services.pricing_service import calculate_surge_pricing
        predictions = [{"hour": h, "load_percent": 0.0, "predicted_bookings": 0.0} for h in range(24)]
        with patch("app.services.pricing_service._current_load_percent", return_value=5.0), \
             patch("app.services.pricing_service._is_weekend_ist", return_value=False):
            result = calculate_surge_pricing(base_price=100.0, predictions=predictions)
        assert result["surge_multiplier"] < 1.0
