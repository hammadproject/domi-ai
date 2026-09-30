import logging
import time
from collections.abc import Callable
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")


def is_rate_limited(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def call_with_429_backoff(fn: Callable[[], T], *, attempts: int = 6, base_delay: float = 5.0) -> T:
    """Run fn, retrying only on rate-limit errors with exponential backoff."""
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_rate_limited(exc) or attempt == attempts:
                raise
            log.warning("gemini 429, backing off %.0fs (attempt %d)", delay, attempt)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")
