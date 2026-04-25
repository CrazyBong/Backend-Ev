from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.review import ReviewCreateRequest, ReviewResponse
from app.services.review_service import create_review, list_station_reviews, get_station_rating_summary

router = APIRouter()

@router.post("", response_model=dict)
async def post_review(
    body: ReviewCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit a new review for a station. Optionally linked to a booking."""
    try:
        review = await create_review(db, user_id=user["sub"], data=body.model_dump())
        return {"success": True, "data": review.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "REVIEW_ERROR", "message": str(e)})

@router.get("/stations/{station_id}", response_model=dict)
async def get_reviews(
    station_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get summarized ratings and list of reviews for a station."""
    reviews = await list_station_reviews(db, str(station_id), limit, offset)
    summary = await get_station_rating_summary(db, str(station_id))
    
    return {
        "success": True,
        "data": {
            "summary": summary,
            "reviews": reviews
        }
    }
