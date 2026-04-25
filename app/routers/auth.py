from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
import time
import uuid

from app.db.database import get_db
from app.schemas.auth import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, TokenPayload, RefreshTokenRequest
from app.services.auth_service import (
    send_otp, verify_otp, blacklist_token, create_access_token, create_refresh_token, user_to_dict,
    OTPRateLimitError, OTPMaxAttemptsError, InvalidOTPError
)
from app.middleware.auth_middleware import get_current_user
from app.config import settings

router = APIRouter()

@router.post("/otp/send", response_model=SendOTPResponse)
async def request_otp(payload: SendOTPRequest):
    try:
        data = await send_otp(payload.phone)
        return SendOTPResponse(**data)
    except OTPRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"code": "OTP_LIMIT_EXCEEDED", "message": str(e), "details": {"retry_after_seconds": e.retry_after_seconds}}
        )

@router.post("/otp/verify", response_model=TokenPayload)
async def confirm_otp(payload: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = await verify_otp(payload.phone, payload.otp, db)
        return TokenPayload(**data)
    except OTPMaxAttemptsError as e:
        raise HTTPException(status_code=401, detail={"code": "INVALID_OTP", "message": str(e), "details": {"attempts_remaining": 0}})
    except InvalidOTPError as e:
        raise HTTPException(status_code=401, detail={"code": "INVALID_OTP", "message": "Incorrect OTP", "details": {"attempts_remaining": e.attempts_remaining}})

@router.post("/token/refresh")
async def refresh_access_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        key = settings.JWT_PUBLIC_KEY.get_secret_value() if hasattr(settings.JWT_PUBLIC_KEY, "get_secret_value") else settings.JWT_PUBLIC_KEY
        decoded = jwt.decode(payload.refresh_token, key, algorithms=[settings.JWT_ALGORITHM])
        
        if decoded.get("type") != "refresh":
            raise jwt.InvalidTokenError("Invalid token type")
            
        user_id = decoded.get("sub")
        parsed_uuid = uuid.UUID(user_id)
        
        from sqlalchemy.future import select
        from app.models.user import User
        
        result = await db.execute(select(User).where(User.id == parsed_uuid))
        user = result.scalars().first()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "User inactive or not found"})
            
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        return {
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "access_token_expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "refresh_token_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                "user": user_to_dict(user)
            }
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED", "message": "Refresh token expired"})
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

@router.delete("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    jti = current_user.get("jti")
    exp = current_user.get("exp")
    if jti and exp:
        await blacklist_token(jti, exp)
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"data": current_user}
