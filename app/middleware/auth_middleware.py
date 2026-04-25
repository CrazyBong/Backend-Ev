from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings
from app.db.redis import get_redis

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify JWT, check blacklist, return user payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Authentication required."})

    token = credentials.credentials
    raw_pub = settings.JWT_PUBLIC_KEY
    if hasattr(raw_pub, "get_secret_value"):
        raw_pub = raw_pub.get_secret_value()
    key = raw_pub.replace("\\n", "\n")
    
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED", "message": "Access token has expired."})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token."})

    # Enforce jti and sub (mandatory for all tokens in this system)
    jti = payload.get("jti")
    sub = payload.get("sub")
    
    if not jti or not sub:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token claims."})

    try:
        # Validate sub is a UUID
        import uuid
        uuid.UUID(sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Malformed user identifier."})


    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token type."})

    # Check blacklist (jti guaranteed to exist by check above)
    redis = await get_redis()
    raw_exists = await redis.exists(f"jwt_blacklist:{jti}")
    if raw_exists:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Token has been revoked."})

    return payload


def require_role(*roles: str):
    async def role_checker(user = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": "Insufficient permissions."}
            )
        return user
    return role_checker

# Convenient role dependencies
require_admin = require_role("station_admin", "super_admin")
require_super_admin = require_role("super_admin")
