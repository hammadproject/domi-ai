import logging
import re
import time
from collections.abc import Callable
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")

MAX_TRANSIENT_ATTEMPTS = 3  # 5xx outages are usually brief; don't hammer a struggling API
MAX_HINT_WAIT_SECONDS = 60  # a chat turn can't wait longer; a bigger hint means "quota gone"

# Gemini reports the wait as e.g. "Please retry in 12.3s" or {"retryDelay": "12s"}
_HINT_PATTERNS = (
    re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.I),
    re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I),
    re.compile(r"retry[- ]after['\"]?\s*[:=]?\s*['\"]?(\d+(?:\.\d+)?)", re.I),
)


def is_rate_limited(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def is_transient_server_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}"
    return any(
        m in text for m in ("ServerError", "503", "UNAVAILABLE", "500 INTERNAL", "overloaded")
    )


def retry_hint_seconds(exc: Exception) -> float | None:
    """Server-suggested wait from a 429 message, if it gave one."""
    text = str(exc)
    for pattern in _HINT_PATTERNS:
        m = pattern.search(text)
        if m:
            return float(m.group(1))
    return None


def call_with_429_backoff(fn: Callable[[], T], *, attempts: int = 6, base_delay: float = 5.0) -> T:
    """Run fn with exponential backoff. Rate limits are retried up to `attempts` times,
    honouring the server's retry hint when present (and giving up at once when the hint
    says to wait longer than a chat turn can); brief 5xx errors up to 3 times. Anything
    else is raised immediately."""
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
            wait = delay
            if limited:
                hint = retry_hint_seconds(exc)
                if hint is not None:
                    if hint > MAX_HINT_WAIT_SECONDS:
                        log.warning("gemini 429 asks for %.0fs wait; giving up", hint)
                        raise
                    wait = max(delay, hint + 1)
            kind = "429" if limited else "5xx"
            log.warning("gemini %s, backing off %.0fs (attempt %d)", kind, wait, attempt)
            time.sleep(wait)
            delay *= 2
    raise RuntimeError("unreachable")
