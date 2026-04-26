import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def seed_slot_for_ws(db_session, seed_station_admin):
    import uuid, json
    from sqlalchemy import text
    
    station_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO stations (id, name, network, location, address, operating_hours, admin_user_id, price_per_unit, is_active, total_slots, available_slots)
        VALUES (:id, 'WS Station', 'TATA_POWER', ST_GeomFromText('POINT(77.4126 23.2599)', 4326), :address, :hours, :admin_id, 15.0, true, 10, 10)
    """), {
        "id": str(station_id),
        "address": json.dumps({"street": "123 Main St"}),
        "hours": json.dumps({"open":"00:00", "close":"23:59", "days":[1,2,3,4,5,6,7]}),
        "admin_id": str(seed_station_admin.id)
    })
    
    slot_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO slots (id, station_id, slot_number, charger_type, power_kw, status)
        VALUES (:id, :station_id, 1, 'CCS2', 50.0, 'AVAILABLE')
    """), {"id": str(slot_id), "station_id": str(station_id)})
    
    await db_session.commit()
    
    class _Slot:
        def __init__(self, s_id, st_id):
            self.id = s_id
            self.station_id = st_id
    
    return _Slot(slot_id, station_id)

class TestPhase12WebSockets:
    async def test_iot_heartbeat_requires_auth(self, client: AsyncClient):
        payload = {
            "slot_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "CHARGING",
            "current_draw_kw": 7.2
        }
        
        # Test completely missing header (FastAPI 422)
        response = await client.post("/v1/iot/heartbeat", json=payload)
        assert response.status_code == 422
        
        # Test wrong header (Our strict 401)
        response2 = await client.post("/v1/iot/heartbeat", json=payload, headers={"X-IoT-Key": "wrong"})
        assert response2.status_code == 401

    async def test_iot_heartbeat_updates_db_and_broadcasts(self, client: AsyncClient, seed_slot_for_ws):
        from app.websockets.manager import manager
        
        slot_id = str(seed_slot_for_ws.id)
        
        # We simulate the websocket since httpx.AsyncClient test client does not natively
        # support standard websockets in this specific framework without Starlette TestClient.
        # So we directly test the endpoints effect on the global manager map.
        
        class MockWebSocket:
            def __init__(self):
                self.messages = []
            async def send_json(self, data):
                self.messages.append(data)
                
        fake_ws = MockWebSocket()
        manager.active_connections[slot_id].add(fake_ws)

        payload = {
            "slot_id": slot_id,
            "status": "CHARGING",
            "current_draw_kw": 7.2
        }
        
        headers = {
            "X-IoT-Key": settings.IOT_API_KEY.get_secret_value()
        }
        
        response = await client.post("/v1/iot/heartbeat", json=payload, headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["new_status"] == "IN_USE" # CHARGING wraps to IN_USE
        
        # Verify the manager fired the message
        assert len(fake_ws.messages) == 1
        ws_msg = fake_ws.messages[0]
        assert ws_msg["event"] == "SLOT_STATUS_CHANGE"
        assert ws_msg["slot_id"] == slot_id
        assert ws_msg["status"] == "IN_USE"
        assert ws_msg["current_draw_kw"] == 7.2

        # Cleanup
        manager.active_connections.pop(slot_id, None)
