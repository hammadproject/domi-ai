import logging
import time
from collections.abc import Callable
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")

MAX_TRANSIENT_ATTEMPTS = 3  # 5xx outages are usually brief; don't hammer a struggling API


def is_rate_limited(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def is_transient_server_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}"
    return any(
        m in text for m in ("ServerError", "503", "UNAVAILABLE", "500 INTERNAL", "overloaded")
    )


def call_with_429_backoff(fn: Callable[[], T], *, attempts: int = 6, base_delay: float = 5.0) -> T:
    """Run fn, retrying rate limits (up to `attempts`) and brief 5xx errors (up to 3)
    with exponential backoff. Anything else is raised immediately."""
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            limited = is_rate_limited(exc)
            transient = is_transient_server_error(exc)
            cap = attempts if limited else min(attempts, MAX_TRANSIENT_ATTEMPTS)
            if not (limited or transient) or attempt >= cap:
                raise
            kind = "429" if limited else "5xx"
            log.warning("gemini %s, backing off %.0fs (attempt %d)", kind, delay, attempt)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")
