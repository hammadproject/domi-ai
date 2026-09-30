import redis as redis_sync
import redis.asyncio as aioredis

from app.config import get_settings

_client: aioredis.Redis | None = None
_sync_client: redis_sync.Redis | None = None
_TIMEOUT = 5


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            get_settings().redis_url,
            socket_timeout=_TIMEOUT,
            socket_connect_timeout=_TIMEOUT,
        )
    return _client


def get_sync_redis() -> redis_sync.Redis:
    """For code that runs in worker threads (the LLM wrapper)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis_sync.Redis.from_url(
            get_settings().redis_url,
            socket_timeout=_TIMEOUT,
            socket_connect_timeout=_TIMEOUT,
        )
    return _sync_client


async def check_redis() -> None:
    """Raise if Redis is unreachable."""
    await get_redis().ping()
