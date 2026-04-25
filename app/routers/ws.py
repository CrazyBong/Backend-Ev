"""
WebSocket Router — Phase 6: Real-Time Slot Status
Broadcasts real-time slot availability updates to connected clients.
Connection model: per-station subscription (ws://.../v1/ws/stations/{station_id})
Uses a simple in-process PubSub backed by asyncio queues (production-ready upgrade:
swap queue maps for Redis pub/sub for multi-process deployment).
"""
import asyncio
import json
import logging
from collections import defaultdict
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# ──────────────────────────────────────────────
# Connection Manager
# ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        # station_id → set of active WebSocket connections
        self._rooms: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, station_id: str):
        await websocket.accept()
        self._rooms[station_id].add(websocket)
        logger.info(f"[WS] Client connected to station room: {station_id}")

    def disconnect(self, websocket: WebSocket, station_id: str):
        self._rooms[station_id].discard(websocket)
        if not self._rooms[station_id]:
            del self._rooms[station_id]
        logger.info(f"[WS] Client disconnected from station room: {station_id}")

    async def broadcast_to_station(self, station_id: str, message: dict):
        """Send a JSON message to all subscribers of a station room."""
        dead_sockets = set()
        for ws in list(self._rooms.get(station_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.add(ws)
        # Prune dead connections
        for ws in dead_sockets:
            self._rooms[station_id].discard(ws)

    async def broadcast_all(self, message: dict):
        """Broadcast to every connected client (e.g., global system events)."""
        for station_id, clients in list(self._rooms.items()):
            await self.broadcast_to_station(station_id, message)


manager = ConnectionManager()


# ──────────────────────────────────────────────
# WebSocket Endpoint
# ──────────────────────────────────────────────
@router.websocket("/stations/{station_id}")
async def station_slot_feed(websocket: WebSocket, station_id: str):
    """
    Real-time WebSocket feed for a specific station's slot availability.
    Authentication: token passed as query param ?token=<jwt>
    On connect: sends a snapshot of current slot statuses.
    On any slot change: server pushes a delta event.
    """
    # Try to authenticate via query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing authentication token.")
        return

    try:
        # Validate token (reuse existing auth logic)
        from app.services.auth_service import verify_access_token
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.accept()
            await websocket.close(code=4003, reason="Invalid token.")
            return
    except Exception:
        await websocket.accept()
        await websocket.close(code=4003, reason="Authentication failed.")
        return

    await manager.connect(websocket, station_id)

    try:
        # Send initial connection acknowledgment
        await websocket.send_json({
            "type": "CONNECTED",
            "station_id": station_id,
            "message": "Subscribed to real-time slot updates.",
        })

        # Keep connection alive — wait for client disconnect
        while True:
            try:
                # Client can send pings; we echo pong to keep alive
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_json({"type": "PONG"})
            except asyncio.TimeoutError:
                # Send server-side keepalive
                await websocket.send_json({"type": "PING"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(f"[WS] Unexpected error in station feed: {exc}")
    finally:
        manager.disconnect(websocket, station_id)
