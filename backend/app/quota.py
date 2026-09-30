"""Global daily LLM-call budget, counted in Redis.

Gemini's daily quota resets at midnight Pacific time, so the counter's day does too. The
budget (LLM_DAILY_CALL_LIMIT) should sit below your real free-tier limit (see AI Studio).
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
PACIFIC = ZoneInfo("America/Los_Angeles")


class QuotaExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("daily LLM call budget used up")
        self.retry_after = retry_after


class QuotaGuard:
    """Sync on purpose: LLM calls run in worker threads."""

    def __init__(self, redis, limit: int, clock: Callable[[], float] = time.time) -> None:
        self._redis, self.limit, self._clock = redis, limit, clock

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), PACIFIC)

    def _key(self) -> str:
        return f"llm:calls:{self._now():%Y-%m-%d}"

    def seconds_until_reset(self) -> int:
        now = self._now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((midnight - now).total_seconds()))

    def used(self) -> int:
        try:
            return int(self._redis.get(self._key()) or 0)
        except Exception:  # noqa: BLE001 - fail open: Gemini's own 429 is the backstop
            log.warning("quota read failed; assuming budget available", exc_info=True)
            return 0

    def remaining(self) -> int:
        return max(0, self.limit - self.used())

    def consume(self) -> int:
        """Count one LLM call; raise QuotaExceeded when the day's budget is spent."""
        try:
            key = self._key()
            count = int(self._redis.incr(key))
            if count == 1:
                self._redis.expire(key, 60 * 60 * 48)
        except Exception:  # noqa: BLE001
            log.warning("quota counter failed; allowing call", exc_info=True)
            return 0
        if count > self.limit:
            raise QuotaExceeded(self.seconds_until_reset())
        return count
