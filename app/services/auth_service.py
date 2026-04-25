import secrets
import time
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from sqlalchemy.future import select

from app.config import settings
from app.db.redis import get_redis
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _get_private_key() -> str:
    """Return the PEM private key with real newlines (dotenv stores \\n as escaped)."""
    raw = settings.JWT_PRIVATE_KEY
    if hasattr(raw, "get_secret_value"):
        raw = raw.get_secret_value()
    return raw.replace("\\n", "\n")


# Redis key patterns
OTP_KEY      = "otp:{phone}"           # TTL = 300s
OTP_ATTEMPTS = "otp_attempts:{phone}"  # TTL = 600s
OTP_RATE     = "otp_rate:{phone}"      # TTL = 600s, max 3
JWT_BLACKLIST = "jwt_blacklist:{jti}"  # TTL = token remaining lifetime

class OTPRateLimitError(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__("OTP rate limit exceeded")

class OTPMaxAttemptsError(Exception):
    def __init__(self):
        super().__init__("Maximum verification attempts reached")

class InvalidOTPError(Exception):
    def __init__(self, attempts_remaining: int):
        self.attempts_remaining = attempts_remaining
        super().__init__("Invalid OTP")


async def send_otp(phone: str) -> dict:
    redis = await get_redis()

    rate_key = OTP_RATE.format(phone=phone)
    raw_count = await redis.get(rate_key)
    count = int(raw_count.decode("utf-8")) if raw_count else 0
    
    if count >= 3:
        ttl = await redis.ttl(rate_key)
        raise OTPRateLimitError(retry_after_seconds=max(0, ttl))

    await redis.incr(rate_key)
    if count == 0:
        await redis.expire(rate_key, 600)

    # Generate cryptographically secure OTP
    otp = "".join([str(secrets.randbelow(10)) for _ in range(settings.OTP_LENGTH)])
    otp_hash = pwd_context.hash(otp)

    # Store in Redis (TTL = 5 min)
    otp_key = OTP_KEY.format(phone=phone)
    await redis.setex(otp_key, settings.OTP_EXPIRE_SECONDS, otp_hash)

    # Reset attempts counter for this OTP session
    attempts_key = OTP_ATTEMPTS.format(phone=phone)
    await redis.delete(attempts_key)

    # For MVP/demo: log to console and return in response (dev only)
    if settings.ENVIRONMENT == "development":
        print(f"[DEV OTP] {phone}: {otp}")

    response_data = {
        "message": "OTP sent successfully",
        "expires_in_seconds": settings.OTP_EXPIRE_SECONDS,
        "phone": phone,
    }
    
    if settings.ENVIRONMENT == "development":
        response_data["_dev_otp"] = otp
        
    return response_data


async def verify_otp(phone: str, otp: str, session) -> dict:
    redis = await get_redis()

    # Check attempts
    attempts_key = OTP_ATTEMPTS.format(phone=phone)
    raw_attempts = await redis.get(attempts_key)
    attempts = int(raw_attempts.decode("utf-8") if raw_attempts else 0)
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPMaxAttemptsError()

    # Check OTP exists
    otp_key = OTP_KEY.format(phone=phone)
    stored_hash = await redis.get(otp_key)
    
    if not stored_hash:
        raise InvalidOTPError(attempts_remaining=settings.OTP_MAX_ATTEMPTS - attempts - 1)
    
    # Explicitly handle bytes from Redis for bcrypt comparison
    if isinstance(stored_hash, bytes):
        stored_hash = stored_hash.decode("utf-8")

    # Increment attempts (before verifying — prevents timing attacks via attempt counting)
    await redis.incr(attempts_key)
    await redis.expire(attempts_key, settings.OTP_RATE_LIMIT_WINDOW)

    # Constant-time comparison via bcrypt
    if not pwd_context.verify(otp, stored_hash):
        remaining = settings.OTP_MAX_ATTEMPTS - (attempts + 1)
        raise InvalidOTPError(attempts_remaining=max(0, remaining))

    # OTP valid — delete it (one-time use)
    await redis.delete(otp_key)

    # Upsert user
    user, is_new = await upsert_user(phone, session)

    # Issue tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    user_data = user_to_dict(user)
    user_data["is_new_user"] = is_new

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "access_token_expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "user": user_data,
    }


async def upsert_user(phone: str, session):
    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalars().first()
    is_new = False
    
    if not user:
        user = User(phone=phone)
        session.add(user)
        is_new = True
        
    await session.flush()
    await session.refresh(user)
    return user, is_new


def user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "phone": user.phone,
        "name": user.name,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
    }


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "jti": secrets.token_urlsafe(16),   # unique token ID for blacklisting
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.JWT_ALGORITHM)


async def blacklist_token(jti: str, exp: int):
    """Store jti in Redis until token expiry."""
    redis = await get_redis()
    ttl = max(0, int(exp - time.time()))
    if ttl > 0:
        await redis.setex(JWT_BLACKLIST.format(jti=jti), ttl, "1")
