"""
Phase 3 integration tests — Station & Slot API.

Auth tokens are generated directly (JWT signed with the app key) without
requiring a DB seed — this lets us test endpoint behaviour against the
real PostGIS/Redis stack without depending on the users table existing.
"""
import uuid
import pytest
from httpx import AsyncClient


# ─── Helpers ──────────────────────────────────────────────────────────────────

TEST_PHONE = "+911234567890"

@pytest.fixture
def station_auth_headers():
    """JWT access token scoped to a fake user — no DB record needed."""
    from app.services.auth_service import create_access_token

    class _FakeUser:
        id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        phone = TEST_PHONE
        role = "user"

    token = create_access_token(_FakeUser())
    return {"Authorization": f"Bearer {token}"}


# ─── Coordinate / radius validation ───────────────────────────────────────────

class TestNearbyStationsValidation:
    """FastAPI rejects clearly invalid query params before hitting the DB."""

    async def test_rejects_lat_too_low(self, client: AsyncClient, station_auth_headers):
        res = await client.get("/v1/stations/nearby?lat=-91&lng=77.0", headers=station_auth_headers)
        assert res.status_code == 422

    async def test_rejects_lat_too_high(self, client: AsyncClient, station_auth_headers):
        res = await client.get("/v1/stations/nearby?lat=91&lng=77.0", headers=station_auth_headers)
        assert res.status_code == 422

    async def test_rejects_lng_too_low(self, client: AsyncClient, station_auth_headers):
        res = await client.get("/v1/stations/nearby?lat=23.0&lng=-181", headers=station_auth_headers)
        assert res.status_code == 422

    async def test_rejects_lng_too_high(self, client: AsyncClient, station_auth_headers):
        res = await client.get("/v1/stations/nearby?lat=23.0&lng=181", headers=station_auth_headers)
        assert res.status_code == 422

    async def test_rejects_radius_above_50km(self, client: AsyncClient, station_auth_headers):
        res = await client.get(
            "/v1/stations/nearby?lat=23.2599&lng=77.4126&radius_km=200",
            headers=station_auth_headers,
        )
        assert res.status_code == 422

    async def test_unauthenticated_request_rejected(self, client: AsyncClient):
        res = await client.get("/v1/stations/nearby?lat=23.2599&lng=77.4126")
        assert res.status_code == 401


# ─── Empty result ─────────────────────────────────────────────────────────────

class TestNearbyStationsEmpty:
    """Ocean coordinates → empty list, never a 500."""

    async def test_returns_empty_for_ocean_coordinates(self, client: AsyncClient, station_auth_headers):
        res = await client.get(
            "/v1/stations/nearby?lat=0.0&lng=0.0&radius_km=10",
            headers=station_auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        assert body["data"] == []


# ─── 404 paths ────────────────────────────────────────────────────────────────

class TestStationDetail:
    async def test_returns_404_for_unknown_station(self, client: AsyncClient, station_auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        res = await client.get(f"/v1/stations/{fake_id}", headers=station_auth_headers)
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "STATION_NOT_FOUND"


class TestSlotDetail:
    async def test_returns_404_for_unknown_slot(self, client: AsyncClient, station_auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        res = await client.get(f"/v1/slots/{fake_id}", headers=station_auth_headers)
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "SLOT_NOT_FOUND"
