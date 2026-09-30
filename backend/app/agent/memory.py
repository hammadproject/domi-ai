"""Per-session conversation memory (merged filters, last shown results, short history)."""

import logging
from typing import Protocol

from pydantic import BaseModel, Field

from app.rag.models import Filters, Hit

log = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_HISTORY = 6


class Turn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SessionState(BaseModel):
    session_id: str
    filters: Filters = Field(default_factory=Filters)
    # Listings shown in the last search, in the order the user saw them ("the first one").
    last_results: list[Hit] = Field(default_factory=list)
    history: list[Turn] = Field(default_factory=list)

    def add_turn(self, user: str, assistant: str) -> None:
        self.history += [Turn(role="user", content=user), Turn(role="assistant", content=assistant)]
        self.history = self.history[-MAX_HISTORY:]


class SessionStore(Protocol):
    async def load(self, session_id: str) -> SessionState: ...
    async def save(self, state: SessionState) -> None: ...


class RedisSessionStore:
    def __init__(self, redis, ttl: int = SESSION_TTL_SECONDS) -> None:
        self._redis, self._ttl = redis, ttl

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    async def load(self, session_id: str) -> SessionState:
        try:
            raw = await self._redis.get(self._key(session_id))
            if raw:
                return SessionState.model_validate_json(raw)
        except Exception:  # noqa: BLE001 - memory loss must not kill the chat
            log.warning("session load failed; starting fresh", exc_info=True)
        return SessionState(session_id=session_id)

    async def save(self, state: SessionState) -> None:
        try:
            await self._redis.set(
                self._key(state.session_id), state.model_dump_json(), ex=self._ttl
            )
        except Exception:  # noqa: BLE001
            log.warning("session save failed", exc_info=True)


class InMemorySessionStore:
    """For tests and local runs without Redis."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def load(self, session_id: str) -> SessionState:
        raw = self._data.get(session_id)
        return SessionState.model_validate_json(raw) if raw else SessionState(session_id=session_id)

    async def save(self, state: SessionState) -> None:
        self._data[state.session_id] = state.model_dump_json()
