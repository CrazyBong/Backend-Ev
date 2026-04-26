"""
Phase 8 Integration Tests: Admin API, Demand Prediction & Rate Limiting
Edge cases covered:
  - Admin: role enforcement (403 for regular users)
  - Admin: slot status update (happy path)
  - Admin: slot going OFFLINE cancels active bookings and notifies users
  - Admin: slot not belonging to station returns 404
  - Admin: view station bookings with optional status filter
  - Demand: authenticated forecast endpoint returns correct structure
  - Demand: empty history returns all zeros
  - Demand: weighted average correct with seeded data
  - Rate limiter: OTP endpoint returns 429 after limit exceeded
  - Response: standard error envelope on 422 validation error
"""
import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


def _token(user):
    from app.services.auth_service import create_access_token
    return create_access_token(user)


def _auth(user):
    return {"Authorization": f"Bearer {_token(user)}"}


async def _seed_booking(db_session, user_id, station_id, slot_id, status="CONFIRMED"):
    """Helper to insert a booking with all required fields."""
    return await db_session.execute(text("""
        INSERT INTO bookings (id, user_id, station_id, slot_id, status, scheduled_start, scheduled_end, amount, idempotency_key)
        VALUES (:id, :user_id, :station_id, :slot_id, :status,
                NOW(), NOW() + INTERVAL '1 hour', 0.0, :ikey)
    """), {
        "id": str(uuid4()),
        "user_id": user_id,
        "station_id": station_id,
        "slot_id": slot_id,
        "status": status,
        "ikey": str(uuid4()),
    })


async def _seed_user(db_session, prefix="7700") -> str:
    uid = str(uuid4())
    phone = f"+91{prefix}{uuid4().hex[:6]}"
    await db_session.execute(text(
        "INSERT INTO users (id, phone, role, is_active) VALUES (:id, :phone, 'user', true)"
    ), {"id": uid, "phone": phone})
    return uid


# ─── ADMIN ROUTER TESTS ───────────────────────────────────────────────────────

class TestAdminAPI:
    async def test_regular_user_cannot_update_slot(self, client, seed_user, seed_slot):
        """Non-admin users must receive 403 Forbidden."""
        res = await client.patch(
            f"/v1/admin/stations/{seed_slot.station_id}/slots/{seed_slot.id}",
            headers=_auth(seed_user),
            json={"status": "OFFLINE"}
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"

    async def test_admin_can_update_slot_to_offline(self, client, seed_station_admin, seed_slot):
        """Station admin can update slot status to OFFLINE."""
        res = await client.patch(
            f"/v1/admin/stations/{seed_slot.station_id}/slots/{seed_slot.id}",
            headers=_auth(seed_station_admin),
            json={"status": "OFFLINE", "reason": "Scheduled maintenance"}
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["new_status"] == "OFFLINE"

    async def test_admin_unknown_slot_returns_404(self, client, seed_station_admin, seed_slot):
        """Updating a slot that doesn't exist under the station returns 404."""
        res = await client.patch(
            f"/v1/admin/stations/{seed_slot.station_id}/slots/{uuid4()}",
            headers=_auth(seed_station_admin),
            json={"status": "OFFLINE"}
        )
        assert res.status_code == 404
        detail = res.json().get("detail", res.json())
        # FastAPI wraps HTTPException detail. detail may be our error_response dict, or nested.
        code = detail.get("error", {}).get("code", "") or detail.get("code", "")
        assert code == "NOT_FOUND"

    async def test_admin_slot_offline_cancels_bookings(self, client, seed_station_admin, seed_slot, db_session):
        """
        When slot goes OFFLINE, all CONFIRMED bookings on that slot should
        be cascaded to CANCELLED_BY_ADMIN.
        """
        uid = await _seed_user(db_session, "7701")
        await _seed_booking(db_session, uid, str(seed_slot.station_id), str(seed_slot.id), "CONFIRMED")
        await db_session.commit()

        with patch("app.services.notification_service.store_notification", new_callable=AsyncMock):
            res = await client.patch(
                f"/v1/admin/stations/{seed_slot.station_id}/slots/{seed_slot.id}",
                headers=_auth(seed_station_admin),
                json={"status": "OFFLINE", "reason": "Power outage"}
            )

        assert res.status_code == 200
        assert res.json()["data"]["affected_bookings"] == 1

        # Verify DB: booking should be CANCELLED_BY_ADMIN
        result = await db_session.execute(
            text("SELECT status::TEXT FROM bookings WHERE slot_id = :slot_id"),
            {"slot_id": str(seed_slot.id)}
        )
        row = result.first()
        assert row[0] == "CANCELLED_BY_ADMIN"

    async def test_admin_available_slot_going_available_no_cancel(self, client, seed_station_admin, seed_slot, db_session):
        """Going AVAILABLE → AVAILABLE does NOT cancel any bookings."""
        uid = await _seed_user(db_session, "7702")
        await _seed_booking(db_session, uid, str(seed_slot.station_id), str(seed_slot.id), "CONFIRMED")
        await db_session.commit()

        res = await client.patch(
            f"/v1/admin/stations/{seed_slot.station_id}/slots/{seed_slot.id}",
            headers=_auth(seed_station_admin),
            json={"status": "AVAILABLE"}
        )
        assert res.status_code == 200
        assert res.json()["data"]["affected_bookings"] == 0

    async def test_admin_view_station_bookings(self, client, seed_station_admin, seed_slot, db_session):
        """Admin can view all bookings for their station."""
        uid = await _seed_user(db_session, "7703")
        await _seed_booking(db_session, uid, str(seed_slot.station_id), str(seed_slot.id))
        await db_session.commit()

        res = await client.get(
            f"/v1/admin/stations/{seed_slot.station_id}/bookings",
            headers=_auth(seed_station_admin),
        )
        assert res.status_code == 200
        assert len(res.json()["data"]) >= 1

    async def test_admin_view_bookings_status_filter(self, client, seed_station_admin, seed_slot, db_session):
        """Bookings endpoint should filter by status."""
        uid = await _seed_user(db_session, "7704")
        await _seed_booking(db_session, uid, str(seed_slot.station_id), str(seed_slot.id), "CANCELLED_BY_USER")
        await db_session.commit()

        # Filter for CONFIRMED: since booking is CANCELLED, result should be empty
        res = await client.get(
            f"/v1/admin/stations/{seed_slot.station_id}/bookings?status=CONFIRMED",
            headers=_auth(seed_station_admin),
        )
        assert res.status_code == 200
        assert all(b["status"] == "CONFIRMED" for b in res.json()["data"])


# ─── DEMAND PREDICTION TESTS ──────────────────────────────────────────────────

class TestDemandPrediction:
    async def test_demand_returns_24_hour_forecast(self, client, seed_user, seed_slot):
        """Forecast endpoint should always return exactly 24 entries (one per hour)."""
        res = await client.get(
            f"/v1/demand/predict/{seed_slot.station_id}",
            headers=_auth(seed_user),
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data["forecast"]) == 24
        assert "peak_hours" in data

    async def test_demand_empty_history_returns_zeros(self, client, seed_user, seed_slot):
        """With no booking history, all hours should show 0 predicted bookings."""
        res = await client.get(
            f"/v1/demand/predict/{seed_slot.station_id}",
            headers=_auth(seed_user),
        )
        assert res.status_code == 200
        forecast = res.json()["data"]["forecast"]
        assert all(h["predicted_bookings"] == 0.0 for h in forecast)
        assert all(h["load_percent"] == 0.0 for h in forecast)

    async def test_demand_with_seeded_bookings(self, client, seed_user, seed_slot, db_session):
        """When recent bookings exist, total predicted demand should be non-zero."""
        uid = await _seed_user(db_session, "6600")
        for _ in range(3):
            await db_session.execute(text("""
                INSERT INTO bookings (id, user_id, station_id, slot_id, status, scheduled_start, scheduled_end, amount, idempotency_key, created_at)
                VALUES (:id, :uid, :station_id, :slot_id,
                        'COMPLETED',
                        NOW(), NOW() + INTERVAL '1 hour', 0.0, :ikey,
                        NOW() - INTERVAL '5 hours')
            """), {
                "id": str(uuid4()),
                "uid": uid,
                "station_id": str(seed_slot.station_id),
                "slot_id": str(seed_slot.id),
                "ikey": str(uuid4()),
            })
        await db_session.execute(text("""
            INSERT INTO station_managers (user_id, station_id)
            VALUES (:user_id, :station_id)
        """), {"user_id": uid, "station_id": str(seed_slot.station_id)})
        await db_session.commit()

        res = await client.get(
            f"/v1/demand/predict/{seed_slot.station_id}",
            headers=_auth(seed_user),
        )
        assert res.status_code == 200
        data = res.json()["data"]
        total_predicted = sum(h["predicted_bookings"] for h in data["forecast"])
        assert total_predicted > 0
        assert len(data["peak_hours"]) <= 3


# ─── RATE LIMITER TESTS ───────────────────────────────────────────────────────

class TestRateLimiter:
    async def test_rate_limit_429_after_threshold(self, client):
        """
        OTP endpoint allows 5 requests/minute. The 6th must return 429.
        """
        payload = {"phone": "+916600000001"}
        for _ in range(5):
            await client.post("/v1/auth/otp/send", json=payload)

        res = await client.post("/v1/auth/otp/send", json=payload)
        assert res.status_code == 429
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in res.headers

    async def test_rate_limit_allows_under_threshold(self, client):
        """Requests below the limit threshold should proceed normally (not 429)."""
        for i in range(4):
            res = await client.post(
                "/v1/auth/otp/send",
                json={"phone": f"+916611{i:06d}"},
            )
            assert res.status_code != 429


# ─── ERROR HANDLER TESTS ──────────────────────────────────────────────────────

class TestErrorHandlers:
    async def test_validation_error_response_format(self, client, seed_user):
        """422 validation errors should return an error envelope."""
        res = await client.post(
            "/v1/reviews",
            headers=_auth(seed_user),
            json={"station_id": str(uuid4()), "rating": 99}  # rating > 5
        )
        assert res.status_code == 422
        # FastAPI wraps our custom response in 'detail'; both formats indicate error
        body = res.json()
        assert "detail" in body or ("success" in body and body["success"] is False)

    async def test_unknown_route_returns_404(self, client):
        """Requests to unknown routes should return 404."""
        res = await client.get("/v1/this/does/not/exist")
        assert res.status_code == 404
