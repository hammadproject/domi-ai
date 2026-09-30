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

from app.api.deps import TurnRunner, get_turn_runner
from app.rag.models import Hit

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


@router.post("/api/chat")
async def chat(req: ChatRequest, run_turn: TurnRunner = Depends(get_turn_runner)):
    session_id = req.session_id or uuid.uuid4().hex

    async def stream() -> AsyncIterator[str]:
        try:
            result = await asyncio.wait_for(
                run_turn(session_id, req.message), timeout=TURN_TIMEOUT_SECONDS
            )
        except TimeoutError:
            log.warning("chat turn timed out")
            yield sse("error", {"code": "timeout", "message": "That took too long. Try again."})
            return
        except Exception:  # noqa: BLE001 - never leak internals to the client
            log.exception("chat turn failed")
            yield sse(
                "error",
                {"code": "internal", "message": "Something went wrong. Please try again shortly."},
            )
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
