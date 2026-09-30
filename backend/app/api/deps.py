"""FastAPI dependencies. Overridable in tests via app.dependency_overrides."""

from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import Depends

from app.agent.graph import AgentDeps, ChatResult, run_chat_turn
from app.agent.memory import RedisSessionStore, SessionStore
from app.cache import Cache
from app.config import get_settings
from app.db import session_scope
from app.llm.counting import CountingLLM
from app.llm.gemini import GeminiClient, LLMClient
from app.observability.tracing import Tracer
from app.quota import QuotaGuard
from app.rag.pipeline import cached_retriever, db_retriever
from app.rag.retrieval import get_hits
from app.redis import get_redis, get_sync_redis

TurnRunner = Callable[[str, str, list[str]], Awaitable[ChatResult]]


@lru_cache
def get_llm_client() -> LLMClient:
    return GeminiClient()


@lru_cache
def get_tracer() -> Tracer:
    return Tracer.from_settings()


def get_session_store() -> SessionStore:
    return RedisSessionStore(get_redis())


def get_cache() -> Cache:
    return Cache(get_redis())


def get_quota_guard() -> QuotaGuard:
    return QuotaGuard(get_sync_redis(), get_settings().llm_daily_call_limit)


def get_turn_runner(
    llm: LLMClient = Depends(get_llm_client),
    store: SessionStore = Depends(get_session_store),
    tracer: Tracer = Depends(get_tracer),
    cache: Cache = Depends(get_cache),
    quota: QuotaGuard = Depends(get_quota_guard),
) -> TurnRunner:
    s = get_settings()

    async def run(session_id: str, message: str, context_ids: list[str]) -> ChatResult:
        async with session_scope() as db:
            deps = AgentDeps(
                llm=CountingLLM(llm, tracer, quota),
                store=store,
                tracer=tracer,
                retriever=cached_retriever(db_retriever(db), cache, s.cache_ttl_seconds),
                cache=cache,
                parse_cache_ttl=s.parse_cache_ttl_seconds,
                hits_fetcher=lambda ids: get_hits(db, ids),
            )
            return await run_chat_turn(deps, session_id, message, context_ids)

    return run
