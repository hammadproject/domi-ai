"""FastAPI dependencies. Overridable in tests via app.dependency_overrides."""

from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import Depends

from app.agent.graph import AgentDeps, ChatResult, run_chat_turn
from app.agent.memory import RedisSessionStore, SessionStore
from app.db import session_scope
from app.llm.counting import CountingLLM
from app.llm.gemini import GeminiClient, LLMClient
from app.observability.tracing import Tracer
from app.rag.pipeline import db_retriever
from app.redis import get_redis

TurnRunner = Callable[[str, str], Awaitable[ChatResult]]


@lru_cache
def get_llm_client() -> LLMClient:
    return GeminiClient()


@lru_cache
def get_tracer() -> Tracer:
    return Tracer.from_settings()


def get_session_store() -> SessionStore:
    return RedisSessionStore(get_redis())


def get_turn_runner(
    llm: LLMClient = Depends(get_llm_client),
    store: SessionStore = Depends(get_session_store),
    tracer: Tracer = Depends(get_tracer),
) -> TurnRunner:
    async def run(session_id: str, message: str) -> ChatResult:
        async with session_scope() as db:
            deps = AgentDeps(
                llm=CountingLLM(llm, tracer),
                store=store,
                tracer=tracer,
                retriever=db_retriever(db),
            )
            return await run_chat_turn(deps, session_id, message)

    return run
