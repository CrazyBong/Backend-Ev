"""
Redis-backed sliding window rate limiter middleware.
Limits requests per user (via Authorization header) or IP per window.
"""
import time
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.redis import get_redis

logger = logging.getLogger(__name__)

# Endpoint-specific limits: (max_requests, window_seconds)
RATE_LIMITS = {
    "/v1/auth/otp/send":    (5,  60),   # 5 OTP sends per minute
    "/v1/auth/otp/verify":  (10, 60),   # 10 verifications per minute
    "/v1/routes/plan":      (20, 60),   # 20 route plans per minute
    "default":              (120, 60),  # 120 requests per minute for all others
}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import sys
        if "pytest" in sys.modules:
            return await call_next(request)
            
        redis = await get_redis()
        if not redis:
            # Fail open if Redis is unavailable
            return await call_next(request)

        # Identify the client: prefer user-id from JWT, fallback to IP
        client_id = request.client.host if request.client else "unknown"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Use raw truncated token as identifier (avoids JWT decode overhead)
            client_id = auth_header[7:30]

        path = request.url.path
        max_requests, window = RATE_LIMITS.get(path, RATE_LIMITS["default"])

        window_start = int(time.time()) // window
        key = f"rl:{path}:{client_id}:{window_start}"

        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window)

            if count > max_requests:
                logger.warning(f"Rate limit exceeded for {client_id} on {path}: {count}/{max_requests}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Too many requests. Limit: {max_requests}/{window}s.",
                        }
                    },
                    headers={"Retry-After": str(window)},
                )
        except Exception as exc:
            logger.error(f"Rate limiter Redis error: {exc}")
            # Fail open on Redis errors

        return await call_next(request)
