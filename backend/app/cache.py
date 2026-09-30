"""Small Redis JSON cache. Fail-open: a cache outage only costs speed, never correctness."""

import hashlib
import json
import logging
from typing import Any

log = logging.getLogger(__name__)
PREFIX = "cache:"


def make_key(namespace: str, *parts: Any) -> str:
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()
    return f"{PREFIX}{namespace}:{digest[:32]}"


class Cache:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            log.warning("cache get failed; treating as miss", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:  # noqa: BLE001
            log.warning("cache set failed", exc_info=True)

    async def clear(self) -> int:
        """Drop every cached entry (used after re-ingesting listings). Sessions and rate-limit
        counters live under other prefixes and are untouched."""
        removed = 0
        try:
            async for key in self._redis.scan_iter(match=f"{PREFIX}*", count=200):
                await self._redis.delete(key)
                removed += 1
        except Exception:  # noqa: BLE001
            log.warning("cache clear failed", exc_info=True)
        return removed
