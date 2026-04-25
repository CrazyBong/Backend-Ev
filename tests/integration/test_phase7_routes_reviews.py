"""
Phase 7 Integration Tests: Route Planner & Reviews
All edge cases covered:
  - Create review (happy path + rating validation)
  - Duplicate review rejection (same user + station)
  - Get reviews with rating summary aggregation
  - Route plan with sufficient range → no stops
  - Route plan with insufficient range → station stop found via PostGIS
"""
import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


def _get_token(user):
    from app.services.auth_service import create_access_token
    return create_access_token(user)


def _auth(user):
    return {"Authorization": f"Bearer {_get_token(user)}"}


# ─── REVIEW TESTS ─────────────────────────────────────────────────────────────

class TestReviewsAPI:
    async def test_create_review_success(self, client, seed_user, seed_slot):
        """Happy path: authenticated user posts a review for a station."""
        res = await client.post(
            "/v1/reviews",
            headers=_auth(seed_user),
            json={
                "station_id": str(seed_slot.station_id),
                "rating": 5,
                "comment": "Excellent station!"
            }
        )
        assert res.status_code == 200
        assert res.json()["success"] is True

    async def test_create_review_rating_out_of_range(self, client, seed_user, seed_slot):
        """Rating must be 1-5; values outside the range are rejected at the schema level."""
        res = await client.post(
            "/v1/reviews",
            headers=_auth(seed_user),
            json={"station_id": str(seed_slot.station_id), "rating": 6}
        )
        assert res.status_code == 422  # Pydantic validation error

    async def test_create_review_no_auth_rejected(self, client, seed_slot):
        """Unauthenticated requests must be rejected with 401."""
        res = await client.post(
            "/v1/reviews",
            json={"station_id": str(seed_slot.station_id), "rating": 3}
        )
        assert res.status_code == 401

    async def test_duplicate_review_rejected(self, client, seed_user, seed_slot, db_session):
        """A second review from the same user for the same station must return 400."""
        # Seed one review directly into DB
        await db_session.execute(text("""
            INSERT INTO reviews (user_id, station_id, rating)
            VALUES (:user_id, :station_id, 4)
        """), {"user_id": str(seed_user.id), "station_id": str(seed_slot.station_id)})
        await db_session.commit()

        # Attempt second review via API
        res = await client.post(
            "/v1/reviews",
            headers=_auth(seed_user),
            json={"station_id": str(seed_slot.station_id), "rating": 3}
        )
        assert res.status_code == 400
        assert "REVIEW_ERROR" in res.json()["detail"]["code"]

    async def test_get_reviews_no_reviews(self, client, seed_slot):
        """Station with no reviews returns empty list, avg=0."""
        res = await client.get(f"/v1/reviews/stations/{seed_slot.station_id}")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["summary"]["total_reviews"] == 0
        assert data["summary"]["avg_rating"] == 0.0

    async def test_get_reviews_with_data(self, client, seed_slot, db_session):
        """Reviews list and average rating calculated correctly from DB data."""
        # Insert two users + two reviews
        user_a_id = str(uuid4())
        user_b_id = str(uuid4())
        for uid, phone in [(user_a_id, "+911100000001"), (user_b_id, "+911100000002")]:
            await db_session.execute(
                text("INSERT INTO users (id, phone, role) VALUES (:id, :phone, 'user')"),
                {"id": uid, "phone": phone}
            )
        await db_session.execute(text("""
            INSERT INTO reviews (user_id, station_id, rating)
            VALUES (:uid_a, :sid, 4)
        """), {"uid_a": user_a_id, "sid": str(seed_slot.station_id)})
        await db_session.execute(text("""
            INSERT INTO reviews (user_id, station_id, rating)
            VALUES (:uid_b, :sid, 2)
        """), {"uid_b": user_b_id, "sid": str(seed_slot.station_id)})
        await db_session.commit()

        res = await client.get(f"/v1/reviews/stations/{seed_slot.station_id}")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["summary"]["total_reviews"] == 2
        assert abs(data["summary"]["avg_rating"] - 3.0) < 0.01  # (4+2)/2 = 3.0
        assert len(data["reviews"]) == 2


# ─── ROUTE PLANNER TESTS ──────────────────────────────────────────────────────

class TestRoutePlannerAPI:

    def _mock_directions(self, total_meters, steps=None):
        """Build a mock Google Directions API response."""
        step_list = steps or [{"distance": {"value": total_meters}, "start_location": {"lat": 0, "lng": 0}}]
        return {
            "routes": [{"legs": [{"distance": {"value": total_meters}, "steps": step_list}]}]
        }

    @patch('httpx.AsyncClient.get')
    async def test_route_sufficient_range_no_stops(self, mock_get, client, seed_user):
        """When battery range exceeds route distance, no charging stops are returned."""
        mock_rsp = MagicMock()
        mock_rsp.json.return_value = self._mock_directions(50_000)  # 50km
        mock_get.return_value = mock_rsp

        res = await client.post(
            "/v1/routes/plan",
            json={
                "origin_lat": 12.97, "origin_lng": 77.59,
                "dest_lat": 13.0, "dest_lng": 77.6,
                "current_battery_percent": 80.0,  # range ≈ 80%*400*0.9=288km > 50km
                "vehicle_range_km": 400.0,
            }
        )
        assert res.status_code == 200
        body = res.json()
        assert body["range_sufficient"] is True
        assert body["charging_stops"] == []
        assert body["total_distance_km"] == pytest.approx(50.0)

    @patch('httpx.AsyncClient.get')
    async def test_route_no_directions_returns_404(self, mock_get, client, seed_user):
        """Empty route response from Google Maps must return 404 ROUTE_NOT_FOUND."""
        mock_rsp = MagicMock()
        mock_rsp.json.return_value = {"routes": []}  # no route
        mock_get.return_value = mock_rsp

        res = await client.post(
            "/v1/routes/plan",
            json={
                "origin_lat": 0.0, "origin_lng": 0.0,
                "dest_lat": 90.0, "dest_lng": 180.0,
                "current_battery_percent": 50.0,
                "vehicle_range_km": 100.0,
            }
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "ROUTE_NOT_FOUND"

    @patch('httpx.AsyncClient.get')
    async def test_route_invalid_battery_rejected(self, mock_get, client, seed_user):
        """Battery percent of 0 or over 100 must be rejected by Pydantic validation."""
        mock_get.return_value = MagicMock()

        for bad_battery in [0, 101, -10]:
            res = await client.post(
                "/v1/routes/plan",
                json={
                    "origin_lat": 12.97, "origin_lng": 77.59,
                    "dest_lat": 13.0, "dest_lng": 77.6,
                    "current_battery_percent": bad_battery,
                    "vehicle_range_km": 200.0,
                }
            )
            assert res.status_code == 422, f"Expected 422 for battery={bad_battery}, got {res.status_code}"

    @patch('httpx.AsyncClient.get')
    async def test_route_insufficient_range_finds_station(self, mock_get, client, seed_user, seed_slot):
        """
        When battery range < route distance, the planner queries PostGIS for
        the nearest station to the point where the battery would fail.
        Our seeded station is at 77.4126, 23.2599, placed exactly at step 2's start_location.
        """
        # Route of 400km; range will be 50%*200*0.9=90km
        # Step 1 ends at 150km — route exceeds range inside step 2
        steps = [
            {"distance": {"value": 150_000}, "start_location": {"lat": 23.0, "lng": 77.0}},
            {"distance": {"value": 250_000}, "start_location": {"lat": 23.2599, "lng": 77.4126}},
        ]
        mock_rsp = MagicMock()
        mock_rsp.json.return_value = self._mock_directions(400_000, steps)
        mock_get.return_value = mock_rsp

        res = await client.post(
            "/v1/routes/plan",
            json={
                "origin_lat": 12.97, "origin_lng": 77.59,
                "dest_lat": 28.70, "dest_lng": 77.10,
                "current_battery_percent": 50.0,  # range=90km < 400km
                "vehicle_range_km": 200.0,
            }
        )
        assert res.status_code == 200
        body = res.json()
        assert body["range_sufficient"] is False
        assert len(body["charging_stops"]) >= 1
        assert body["charging_stops"][0]["station_id"] == str(seed_slot.station_id)

    @patch('httpx.AsyncClient.get')
    async def test_route_result_is_cached(self, mock_get, client, seed_user):
        """
        Making the same route request twice should only call Google Maps once
        (second response served from Redis cache).
        """
        mock_rsp = MagicMock()
        mock_rsp.json.return_value = self._mock_directions(30_000)  # 30km
        mock_get.return_value = mock_rsp

        payload = {
            "origin_lat": 12.97, "origin_lng": 77.59,
            "dest_lat": 13.00, "dest_lng": 77.60,
            "current_battery_percent": 90.0,
            "vehicle_range_km": 300.0,
        }
        await client.post("/v1/routes/plan", json=payload)
        await client.post("/v1/routes/plan", json=payload)

        # Google Maps API called only once, second hit uses cache
        assert mock_get.call_count == 1
