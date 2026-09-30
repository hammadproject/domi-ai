"""Langfuse tracing: one trace per chat request, one span per graph node.

Tracing is strictly best-effort: with no keys configured it is a silent no-op, and any
Langfuse error is swallowed so observability can never break a chat turn.
"""

import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)


class SpanHandle:
    """What callers get inside `with tracer.span(...)`; update() is safe to call always."""

    def __init__(self, obs: Any = None) -> None:
        self._obs = obs

    def update(self, **kwargs: Any) -> None:
        if self._obs is None:
            return
        try:
            self._obs.update(**kwargs)
        except Exception:  # noqa: BLE001 - tracing must never raise
            log.debug("span update failed", exc_info=True)


class TraceHandle(SpanHandle):
    def __init__(self, obs: Any = None, trace_id: str | None = None, url: str | None = None):
        super().__init__(obs)
        self.trace_id = trace_id
        self.url = url


class Tracer:
    def __init__(self, client: Any = None) -> None:
        self._client = client

    @classmethod
    def from_settings(cls) -> "Tracer":
        s = get_settings()
        secret = s.langfuse_secret_key.get_secret_value()
        if not (s.langfuse_public_key and secret):
            log.info("langfuse keys not set: tracing disabled")
            return cls(None)
        try:
            from langfuse import Langfuse

            kwargs = {"host": s.langfuse_host} if s.langfuse_host else {}
            return cls(Langfuse(public_key=s.langfuse_public_key, secret_key=secret, **kwargs))
        except Exception:  # noqa: BLE001
            log.warning("langfuse init failed: tracing disabled", exc_info=True)
            return cls(None)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @contextmanager
    def trace(self, name: str, *, session_id: str, input: Any = None) -> Iterator[TraceHandle]:
        if self._client is None:
            yield TraceHandle()
            return
        stack = ExitStack()
        try:
            from langfuse import propagate_attributes

            stack.enter_context(propagate_attributes(session_id=session_id))
            obs = stack.enter_context(
                self._client.start_as_current_observation(name=name, as_type="span", input=input)
            )
            trace_id = self._client.get_current_trace_id()
            url = self._client.get_trace_url(trace_id=trace_id) if trace_id else None
            handle = TraceHandle(obs, trace_id, url)
        except Exception:  # noqa: BLE001 - setup failed: run the caller untraced
            log.warning("tracing setup failed", exc_info=True)
            stack.close()
            yield TraceHandle()
            return
        with stack:  # exceptions from the traced body propagate normally
            yield handle

    @contextmanager
    def span(self, name: str, *, input: Any = None, as_type: str = "span") -> Iterator[SpanHandle]:
        if self._client is None:
            yield SpanHandle()
            return
        stack = ExitStack()
        try:
            obs = stack.enter_context(
                self._client.start_as_current_observation(name=name, as_type=as_type, input=input)
            )
            handle = SpanHandle(obs)
        except Exception:  # noqa: BLE001
            log.warning("span setup failed", exc_info=True)
            stack.close()
            yield SpanHandle()
            return
        with stack:
            yield handle

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:  # noqa: BLE001
                log.debug("langfuse flush failed", exc_info=True)


NOOP = Tracer(None)
