"""POST /api/chat: Server-Sent Events. Events: listings, token, done, error."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.api.deps import TurnRunner, get_quota_guard, get_turn_runner
from app.config import get_settings
from app.errors import HIGH_DEMAND_MESSAGE, HighDemandError
from app.llm.retry import is_rate_limited
from app.quota import QuotaExceeded, QuotaGuard
from app.rag.models import Hit
from app.ratelimit import RateLimiter, get_rate_limiter, limit_chat_ip

router = APIRouter()
log = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 60
WORDS_PER_TOKEN_EVENT = 3
SESSION_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, pattern=SESSION_ID_PATTERN)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def listing_payload(rank: int, h: Hit) -> dict[str, Any]:
    d = h.model_dump(exclude={"listing_card"})
    return {"rank": rank, **d}


def token_chunks(text: str) -> list[str]:
    words = re.findall(r"\S+\s*", text)
    return ["".join(words[i : i + WORDS_PER_TOKEN_EVENT]) for i in range(0, len(words), 3)]


def failure_event(exc: BaseException) -> str:
    """Map a failed turn to a safe, friendly SSE error event (never leaks internals)."""
    if isinstance(exc, QuotaExceeded):
        return sse(
            "error",
            {"code": "high_demand", "message": HIGH_DEMAND_MESSAGE, "retry_after": exc.retry_after},
        )
    if isinstance(exc, TimeoutError):
        return sse("error", {"code": "timeout", "message": "That took too long. Try again."})
    if isinstance(exc, Exception) and is_rate_limited(exc):  # Gemini's own 429 after retries
        return sse("error", {"code": "high_demand", "message": HIGH_DEMAND_MESSAGE})
    return sse(
        "error", {"code": "internal", "message": "Something went wrong. Please try again shortly."}
    )


@router.post("/api/chat", dependencies=[Depends(limit_chat_ip)])
async def chat(
    req: ChatRequest,
    run_turn: TurnRunner = Depends(get_turn_runner),
    limiter: RateLimiter = Depends(get_rate_limiter),
    quota: QuotaGuard = Depends(get_quota_guard),
):
    if req.session_id:  # per-session limit on top of the per-IP one
        await limiter.check(
            "chat-session", req.session_id, get_settings().chat_rate_limit_per_minute
        )
    # Degrade before spending anything if today's LLM budget is gone (HTTP 503 + Retry-After).
    if await asyncio.to_thread(quota.remaining) <= 0:
        raise HighDemandError(retry_after=quota.seconds_until_reset())

    session_id = req.session_id or uuid.uuid4().hex

    async def stream() -> AsyncIterator[str]:
        try:
            result = await asyncio.wait_for(
                run_turn(session_id, req.message), timeout=TURN_TIMEOUT_SECONDS
            )
        except Exception as exc:  # noqa: BLE001 - TimeoutError included
            if isinstance(exc, QuotaExceeded | TimeoutError):
                log.warning("chat turn ended early: %s", type(exc).__name__)
            else:
                log.exception("chat turn failed")
            yield failure_event(exc)
            return

        if result.trace_url:
            log.info("langfuse trace: %s", result.trace_url)
        yield sse(
            "listings",
            {
                "listings": [listing_payload(rank, h) for rank, h in result.shown],
                "highlight_ids": [h.id for _, h in result.shown],
            },
        )
        for chunk in token_chunks(result.text):
            yield sse("token", {"text": chunk})
            await asyncio.sleep(0)
        yield sse(
            "done",
            {
                "session_id": result.session_id,
                "intent": result.intent,
                "llm_calls": result.llm_calls,
                "refused": result.refused,
                "degraded": result.degraded,
                "trace_id": result.trace_id,
            },
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
