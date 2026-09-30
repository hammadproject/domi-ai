"""Redis sliding-window rate limiting per IP and (for chat) per session.

Returns 429 with a Retry-After header. Fails OPEN if Redis is down: an outage must not
take the API down with it (the daily LLM budget still protects the quota).
"""

import logging
import time
from collections.abc import Callable

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import RateLimitError
from app.redis import get_redis

log = logging.getLogger(__name__)
WINDOW_SECONDS = 60


class RateLimiter:
    """Sliding-window counter: the previous minute's hits are weighted by how much of it
    still overlaps the last 60 seconds. This closes the fixed-window loophole where a client
    sends `limit` requests just before a minute boundary and `limit` more just after.
    One pipelined Redis round trip per check."""

    def __init__(self, redis, clock: Callable[[], float] = time.time) -> None:
        self._redis, self._clock = redis, clock

    async def check(self, scope: str, ident: str, limit: int) -> None:
        now = self._clock()
        window = int(now // WINDOW_SECONDS)
        current = f"rl:{scope}:{ident}:{window}"
        previous = f"rl:{scope}:{ident}:{window - 1}"
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.incr(current)
                pipe.get(previous)
                pipe.expire(current, WINDOW_SECONDS * 2)
                count, prev_raw, _ = await pipe.execute()
        except Exception:  # noqa: BLE001
            log.warning("rate limiter unavailable; allowing request", exc_info=True)
            return
        elapsed = (now % WINDOW_SECONDS) / WINDOW_SECONDS
        estimated = int(count) + int(prev_raw or 0) * (1 - elapsed)
        if estimated > limit:
            retry_after = max(1, int((window + 1) * WINDOW_SECONDS - now))
            log.warning("rate limited: scope=%s estimated=%.1f limit=%d", scope, estimated, limit)
            raise RateLimitError(
                f"Too many requests. Try again in {retry_after} seconds.", retry_after=retry_after
            )


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis())


async def limit_api(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
    """General per-IP limit for /api routes."""
    s = get_settings()
    await limiter.check("api", client_ip(request, s), s.rate_limit_per_minute)


async def limit_chat_ip(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
    s = get_settings()
    await limiter.check("chat-ip", client_ip(request, s), s.chat_rate_limit_per_minute)
