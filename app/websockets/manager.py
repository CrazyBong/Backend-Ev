from fastapi import WebSocket
from collections import defaultdict
from typing import DefaultDict, Set
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # slot_id → set of connected WebSocket clients
        self.active_connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, slot_id: str):
        await websocket.accept()
        self.active_connections[slot_id].add(websocket)
        logger.info(f"WebSocket client connected to slot {slot_id}. Total clients: {self.connection_count(slot_id)}")

    def disconnect(self, websocket: WebSocket, slot_id: str):
        self.active_connections[slot_id].discard(websocket)
        # Cleanup empty sets safely
        if not self.active_connections[slot_id]:
            self.active_connections.pop(slot_id, None)
        logger.info(f"WebSocket client disconnected from slot {slot_id}. Total clients: {self.connection_count(slot_id)}")

    async def broadcast_to_slot(self, slot_id: str, message: dict):
        connections = self.active_connections.get(slot_id, set())
        if not connections:
            logger.info(f"Broadcast to slot {slot_id} skipped: No active connections.")
            return

        dead = set()
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                dead.add(websocket)   # Mark dead connections
        
        # Clean up dead connections
        for websocket in dead:
            self.disconnect(websocket, slot_id)

    def connection_count(self, slot_id: str) -> int:
        return len(self.active_connections.get(slot_id, set()))

# Singleton — one instance for the entire app lifetime
manager = WebSocketManager()
