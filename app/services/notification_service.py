"""
In-App Notification Service — Phase 6
Stores in-app notifications in DB + optionally sends Expo push notifications.
Designed to never block the booking flow: all failures are logged, not raised.
"""
import json
import logging
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


# ─────────────────────────────────────────
# Push Notification (Expo)
# ─────────────────────────────────────────

async def send_push_notification(
    expo_push_token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> bool:
    """Send push notification via Expo Push API. Never raises."""
    payload = {
        "to": expo_push_token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": data or {},
        "priority": "high",
        "channelId": "bookings",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.EXPO_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            # Expo returns a list of tickets inside 'data'
            tickets = res.json().get("data", [])
            if isinstance(tickets, list) and tickets:
                ticket = tickets[0]
                if isinstance(ticket, dict) and ticket.get("status") == "error":
                    logger.warning(f"[Push] Expo error: {ticket}")
                    return False
            return True
    except Exception as exc:
        logger.error(f"[Push] Notification failed — {exc}")
        return False


# ─────────────────────────────────────────
# In-App Notification (DB)
# ─────────────────────────────────────────

async def store_notification(
    db: AsyncSession,
    user_id: str,
    notif_type: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """Insert a notification row that the client can poll/receive via WebSocket."""
    try:
        import uuid as _uuid
        await db.execute(text("""
            INSERT INTO notifications (id, user_id, type, title, body, data)
            VALUES (:id, :user_id, :type, :title, :body, :data)
        """), {
            "id": str(_uuid.uuid4()),
            "user_id": user_id,
            "type": notif_type,
            "title": title,
            "body": body,
            "data": json.dumps(data or {}),
        })
        if not db.in_transaction():
            await db.commit()
    except Exception as exc:
        logger.error(f"[Notification] Failed to store in-app notification: {exc}")
        if not db.in_transaction():
            await db.rollback()


# ─────────────────────────────────────────
# High-Level Helpers
# ─────────────────────────────────────────

async def notify_booking_confirmed(
    db: AsyncSession,
    user_id: str,
    booking_id: str,
    expo_push_token: str | None = None,
) -> None:
    title = "⚡ Booking Confirmed!"
    body = f"Your slot is locked in. Booking #{booking_id[:8].upper()} — Scan QR at the station."
    data = {"type": "BOOKING_CONFIRMED", "booking_id": booking_id}

    await store_notification(db, user_id, "BOOKING_CONFIRMED", title, body, data)
    if expo_push_token:
        await send_push_notification(expo_push_token, title, body, data)


async def notify_booking_cancelled(
    db: AsyncSession,
    user_id: str,
    booking_id: str,
    reason: str = "Cancelled",
    expo_push_token: str | None = None,
) -> None:
    title = "Booking Cancelled"
    body = f"Booking #{booking_id[:8].upper()} has been cancelled. {reason}"
    data = {"type": "BOOKING_CANCELLED", "booking_id": booking_id}

    await store_notification(db, user_id, "BOOKING_CANCELLED", title, body, data)
    if expo_push_token:
        await send_push_notification(expo_push_token, title, body, data)


async def notify_slot_available(
    db: AsyncSession,
    user_id: str,
    station_id: str,
    slot_id: str,
    expo_push_token: str | None = None,
) -> None:
    title = "🔌 Slot Now Available!"
    body = "A charging slot at your saved station just became available."
    data = {"type": "SLOT_AVAILABLE", "station_id": station_id, "slot_id": slot_id}
    
    await store_notification(db, user_id, "SLOT_AVAILABLE", title, body, data)
    if expo_push_token:
        await send_push_notification(expo_push_token, title, body, data)
