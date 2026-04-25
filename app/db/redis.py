import redis.asyncio as redis
from app.config import settings

redis_pool: redis.Redis | None = None

async def init_redis_pool():
    global redis_pool
    if redis_pool is not None:
        return
    redis_pool = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

async def close_redis_pool():
    global redis_pool
    if redis_pool:
        await redis_pool.aclose()
        redis_pool = None

async def get_redis() -> redis.Redis:
    global redis_pool
    if redis_pool is None:
        await init_redis_pool()
    return redis_pool
