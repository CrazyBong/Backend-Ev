from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websockets.manager import manager
import jwt
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/slot/{slot_id}")
async def slot_websocket(websocket: WebSocket, slot_id: str, token: str | None = Query(None)):
    """
    WebSocket endpoint for frontend/mobile apps to subscribe to slot status changes.
    Pass token as query param for auth.
    """
    if token:
        try:
            raw_pub = settings.JWT_PUBLIC_KEY
            if hasattr(raw_pub, "get_secret_value"):
                raw_pub = raw_pub.get_secret_value()
            key = raw_pub.replace("\\n", "\n")
            jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
        except Exception as e:
            logger.warning(f"WebSocket auth failed: {e}")
            await websocket.accept()
            await websocket.close(code=1008)  # Policy Violation
            return

    await manager.connect(websocket, slot_id)
    
    try:
        # Send immediate current state on connect
        await websocket.send_json({
            "event": "CONNECTED",
            "slot_id": slot_id,
            "message": "Subscribed to slot updates"
        })
        
        while True:
            # Keep connection alive — ping/pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket cleanly disconnected for slot {slot_id}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for slot {slot_id}: {e}")
    finally:
        manager.disconnect(websocket, slot_id)
