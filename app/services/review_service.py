import logging
from sqlalchemy import text
from app.models.review import Review

logger = logging.getLogger(__name__)

async def create_review(db, user_id: str, data: dict):
    from sqlalchemy.exc import IntegrityError

    station_id = data["station_id"]
    booking_id = data.get("booking_id")

    # Explicit pre-check: one review per user per station
    existing = await db.execute(text("""
        SELECT id FROM reviews WHERE user_id = :user_id AND station_id = :station_id LIMIT 1
    """), {"user_id": user_id, "station_id": str(station_id)})
    if existing.first():
        raise ValueError("User has already reviewed this station.")

    try:
        new_review = Review(
            user_id=user_id,
            station_id=station_id,
            booking_id=booking_id,
            rating=data["rating"],
            comment=data.get("comment")
        )
        db.add(new_review)
        await db.commit()
        await db.refresh(new_review)
        return new_review
    except IntegrityError:
        await db.rollback()
        raise ValueError("Review constraint violation.")

async def list_station_reviews(db, station_id: str, limit: int = 50, offset: int = 0):
    result = await db.execute(text("""
        SELECT r.id, r.user_id, r.station_id, r.booking_id, r.rating, r.comment, r.created_at, 
               CONCAT('******', RIGHT(u.phone, 4)) AS phone_masked
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.station_id = :station_id
        ORDER BY r.created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"station_id": station_id, "limit": limit, "offset": offset})
    
    return [dict(row) for row in result.mappings()]

async def get_station_rating_summary(db, station_id: str):
    result = await db.execute(text("""
        SELECT AVG(rating) as avg_rating, COUNT(*) as total_reviews
        FROM reviews
        WHERE station_id = :station_id
    """), {"station_id": station_id})
    row = result.mappings().first()
    return {
        "avg_rating": float(row["avg_rating"]) if row["avg_rating"] else 0.0,
        "total_reviews": int(row["total_reviews"]) if row["total_reviews"] else 0
    }
