"""
Notifications Router — Phase 6
Provides REST endpoints for in-app notification management:
  GET  /v1/notifications          — List user's notifications (unread first)
  POST /v1/notifications/{id}/read — Mark a notification as read
  POST /v1/notifications/read-all  — Mark all as read  
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.get("", response_model=dict)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List the 50 most recent notifications for the authenticated user."""
    result = await db.execute(text("""
        SELECT
            id::text, type, title, body, data,
            is_read, created_at
        FROM notifications
        WHERE user_id = :user_id
        ORDER BY is_read ASC, created_at DESC
        LIMIT 50
    """), {"user_id": user["sub"]})

    notifications = [dict(row) for row in result.mappings()]
    
    count_res = await db.execute(text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = FALSE"), {"user_id": user["sub"]})
    unread_count = count_res.scalar()

    return {
        "data": notifications,
        "meta": {"unread_count": unread_count},
    }


@router.post("/{notification_id}/read", response_model=dict)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Mark a single notification as read. Returns 404 if not found or not owned."""
    result = await db.execute(text("""
        UPDATE notifications
        SET is_read = TRUE
        WHERE id = :id AND user_id = :user_id
        RETURNING id
    """), {"id": str(notification_id), "user_id": user["sub"]})

    if not result.first():
        raise HTTPException(
            status_code=404,
            detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification not found."},
        )

    await db.commit()
    return {"data": {"status": "read"}}


@router.post("/read-all", response_model=dict)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Mark all unread notifications as read for the current user."""
    result = await db.execute(text("""
        UPDATE notifications
        SET is_read = TRUE
        WHERE user_id = :user_id AND is_read = FALSE
        RETURNING id
    """), {"user_id": user["sub"]})

    updated_count = len(result.fetchall())
    await db.commit()
    return {"data": {"marked_read": updated_count}}
