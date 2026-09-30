import redis.asyncio as aioredis

from app.config import get_settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_settings().redis_url, socket_timeout=5)
    return _client


async def check_redis() -> None:
    """Raise if Redis is unreachable."""
    await get_redis().ping()
