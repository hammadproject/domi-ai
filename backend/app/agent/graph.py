"""LangGraph agent (plan 8.1):

input_guard -> understand(router+parser, ONE LLM call) -> {search | mortgage_tool |
compare_tool | smalltalk} -> generate -> output_guard -> finalize (memory) -> stream

LLM budget per normal turn: 1 (understand) + 1 (grounded generation for search) = 2.
Tools and small talk are deterministic, so they cost 1 call. Clear guardrail refusals cost 0.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent import formatting as fmt
from app.agent.generate import generate_grounded, validate_ids
from app.agent.memory import SessionState, SessionStore
from app.agent.understanding import TurnUnderstanding, understand
from app.cache import Cache, make_key
from app.guardrails.input_guard import InputGuardResult, check_input
from app.guardrails.output_guard import check_output
from app.llm.counting import CountingLLM
from app.observability.tracing import Tracer
from app.rag.models import Filters, Hit, SearchResult
from app.rag.pipeline import Retriever, run_search
from app.rag.query_parser import merge_filters
from app.rag.rerank import ScoreFn, cross_encoder_scores
from app.tools.compare import compare_listings
from app.tools.mortgage import (
    MortgageAssumptions,
    affordability,
    compare_terms,
    down_payment_scenarios,
    estimate_payment,
)

log = logging.getLogger(__name__)
DEFAULT_DOWN_PCT = 20.0


@dataclass
class AgentDeps:
    llm: CountingLLM
    store: SessionStore
    tracer: Tracer
    retriever: Retriever
    score_fn: ScoreFn = cross_encoder_scores
    cache: Cache | None = None
    parse_cache_ttl: int = 3600
    # ids -> listings, for chat requests that say which homes the user is looking at
    hits_fetcher: Callable[[list[str]], Awaitable[list[Hit]]] | None = None


class AgentState(TypedDict, total=False):
    message: str
    session: SessionState
    guard: InputGuardResult
    refused: bool
    understanding: TurnUnderstanding
    requested_filters: Filters
    search: SearchResult
    draft: str
    shown: list[tuple[int, Hit]]  # (rank in the list the user sees, listing)
    intent: str
    degraded: bool
    final: str
    output_flags: list[str]


@dataclass
class ChatResult:
    session_id: str
    text: str
    shown: list[tuple[int, Hit]]
    intent: str
    llm_calls: int
    refused: bool = False
    degraded: bool = False
    guard_categories: list[str] = field(default_factory=list)
    trace_id: str | None = None
    trace_url: str | None = None


def _brief(value: Any) -> Any:
    """Small JSON-safe summary of node outputs for trace spans."""
    if hasattr(value, "model_dump"):
        return _brief(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return {k: _brief(v) for k, v in list(value.items())[:12]}
    if isinstance(value, list):
        return [_brief(v) for v in value[:5]] + (["..."] if len(value) > 5 else [])
    if isinstance(value, tuple):
        return _brief(list(value))
    if isinstance(value, str):
        return value[:300]
    return value


def _hits_by_position(u: TurnUnderstanding, session: SessionState) -> list[tuple[int, Hit]]:
    last = session.last_results
    picked = [(p, last[p - 1]) for p in dict.fromkeys(u.listing_positions) if 1 <= p <= len(last)]
    return picked[:3]


def build_graph(deps: AgentDeps):  # noqa: C901 - one flat node table reads best
    def traced(name: str, fn):
        async def wrapper(state: AgentState) -> dict[str, Any]:
            with deps.tracer.span(name) as span:
                span.update(input=_brief({"message": state.get("message")}))
                update = await fn(state)
                span.update(output=_brief({k: v for k, v in update.items() if k != "session"}))
                return update

        return wrapper

    async def _cached_understand(message: str, session: SessionState) -> TurnUnderstanding:
        """The routing+parse call, memoized. The key covers everything the prompt depends on
        (message, current filters, the shown listings), so a hit is always equivalent."""
        if deps.cache is None:
            return await asyncio.to_thread(understand, message, session, deps.llm)
        key = make_key(
            "parse",
            message.strip().lower(),
            session.filters.active(),
            [h.id for h in session.last_results],
        )
        cached = await deps.cache.get(key)
        if cached is not None:
            try:
                return TurnUnderstanding.model_validate(cached)
            except ValueError:
                log.warning("bad parse-cache entry ignored")
        u = await asyncio.to_thread(understand, message, session, deps.llm)
        await deps.cache.set(key, u.model_dump(), deps.parse_cache_ttl)
        return u

    # ---- nodes ----
    async def input_guard(state: AgentState) -> dict[str, Any]:
        res = await asyncio.to_thread(check_input, state["message"], llm=deps.llm)
        if res.action == "refuse":
            return {"guard": res, "refused": True, "draft": res.reply or "", "intent": "refused"}
        return {"guard": res, "refused": False}

    async def understand_node(state: AgentState) -> dict[str, Any]:
        session = state["session"]
        u = await _cached_understand(state["message"], session)
        requested = merge_filters(session.filters, u) if u.intent == "search" else session.filters
        return {"understanding": u, "requested_filters": requested, "intent": u.intent}

    def route(state: AgentState) -> str:
        return {
            "search": "search",
            "mortgage": "mortgage_tool",
            "compare": "compare_tool",
        }.get(state["understanding"].intent, "smalltalk")

    async def search_node(state: AgentState) -> dict[str, Any]:
        u = state["understanding"]
        res = await run_search(
            state["requested_filters"],
            u.semantic_query,
            retriever=deps.retriever,
            score_fn=deps.score_fn,
        )
        update: dict[str, Any] = {
            "search": res,
            "shown": [(i, r.hit) for i, r in enumerate(res.results, 1)],
        }
        if not res.results:  # nothing to ground an LLM answer on: deterministic, no call
            update["draft"] = res.message
        return update

    async def mortgage_node(state: AgentState) -> dict[str, Any]:
        u, session = state["understanding"], state["session"]
        a = u.mortgage
        hits = _hits_by_position(u, session)
        if not hits and a.price is None and len(session.last_results) == 1:
            hits = [(1, session.last_results[0])]
        assumptions = MortgageAssumptions.from_settings()
        if a.interest_rate is not None:
            assumptions = assumptions.model_copy(update={"interest_rate": a.interest_rate})
        term = a.term_years or 30
        try:
            if a.kind == "affordability":
                if not a.annual_income or a.down_payment is None:
                    return {
                        "draft": "To estimate how much home you can afford I need your annual "
                        "income and how much you can put down (in dollars). Monthly debts help "
                        "too."
                    }
                res = affordability(
                    annual_income=a.annual_income,
                    down_payment=a.down_payment,
                    monthly_debts=a.monthly_debts or 0.0,
                    hoa_monthly=a.hoa_monthly or 0.0,
                    term_years=term,
                    assumptions=assumptions,
                )
                return {"draft": fmt.with_disclaimer(fmt.affordability_text(res))}

            targets: list[tuple[float, float, str | None]] = []  # price, hoa, label
            if a.price is not None:
                targets.append((a.price, a.hoa_monthly or 0.0, None))
            else:
                for _rank, h in hits:
                    if h.price:
                        targets.append((h.price, a.hoa_monthly or h.hoa_fee or 0.0, h.address))
            if not targets:
                return {
                    "draft": "Which home should I estimate? Give me a price, or tell me which "
                    "listing (for example 'the first one')."
                }
            down_kw: dict[str, float | None] = {
                "down_payment": a.down_payment,
                "down_payment_pct": a.down_payment_pct,
            }
            assumed_default = a.down_payment is None and a.down_payment_pct is None
            if assumed_default:
                down_kw["down_payment_pct"] = DEFAULT_DOWN_PCT
            texts = []
            for price, hoa, label in targets:
                if a.kind == "scenarios":
                    texts.append(
                        fmt.scenarios_text(
                            down_payment_scenarios(
                                price, hoa_monthly=hoa, term_years=term, assumptions=assumptions
                            )
                        )
                    )
                elif a.kind == "term_compare":
                    texts.append(
                        fmt.terms_text(
                            compare_terms(
                                price, hoa_monthly=hoa, assumptions=assumptions, **down_kw
                            )
                        )
                    )
                else:
                    b = estimate_payment(
                        price, hoa_monthly=hoa, term_years=term, assumptions=assumptions, **down_kw
                    )
                    texts.append(fmt.payment_text(b, label))
            body = "\n\n".join(texts)
            if assumed_default and a.kind != "scenarios":
                body += (
                    f"\n(I assumed {DEFAULT_DOWN_PCT:g}% down; tell me another amount to update.)"
                )
            shown = [(r, h) for r, h in hits if h.price] if a.price is None else []
            return {"draft": fmt.with_disclaimer(body), "shown": shown}
        except ValueError as exc:
            return {"draft": f"I couldn't compute that estimate: {exc}."}

    async def compare_node(state: AgentState) -> dict[str, Any]:
        hits = _hits_by_position(state["understanding"], state["session"])
        if len(hits) < 2:
            return {
                "draft": "Tell me which two or three of the listings I showed you to compare "
                "(for example 'compare the first two')."
            }
        comparison = compare_listings(
            [h for _, h in hits], assumptions=MortgageAssumptions.from_settings()
        )
        return {"draft": fmt.comparison_text(comparison), "shown": hits}

    async def smalltalk_node(state: AgentState) -> dict[str, Any]:
        return {"draft": fmt.SMALLTALK_REPLY}

    async def generate_node(state: AgentState) -> dict[str, Any]:
        if state.get("draft"):  # tools, small talk, no-results already produced text
            return {}
        res = state["search"]
        ranked = res.results
        note = res.message if res.relaxations else ""
        try:
            ga = await asyncio.to_thread(
                generate_grounded, state["message"], note, ranked, deps.llm
            )
        except Exception as exc:  # noqa: BLE001 - quota/network: degrade, don't fail the turn
            log.warning("generation failed (%s); using deterministic answer", type(exc).__name__)
            return {"draft": fmt.search_fallback_text(res.message, ranked), "degraded": True}
        keep = set(validate_ids(ga, ranked))
        shown = [(i, h) for i, h in state["shown"] if h.id in keep] or state["shown"]
        return {"draft": ga.answer, "shown": shown}

    async def output_guard_node(state: AgentState) -> dict[str, Any]:
        res = check_output(state["draft"])
        return {"final": res.text, "output_flags": [v.category for v in res.violations]}

    async def finalize(state: AgentState) -> dict[str, Any]:
        session = state["session"]
        text = state.get("final") or state.get("draft", "")
        if state.get("intent") == "search":
            session.filters = state["requested_filters"]  # keep what the user asked, not relaxed
            ranked = state["search"].results
            if ranked:
                session.last_results = [
                    r.hit.model_copy(update={"listing_card": None}) for r in ranked
                ]
        session.add_turn(state["message"], text)
        await deps.store.save(session)
        return {"final": text}

    g = StateGraph(AgentState)
    g.add_node("input_guard", traced("input_guard", input_guard))
    g.add_node("understand", traced("understand", understand_node))
    g.add_node("search", traced("search", search_node))
    g.add_node("mortgage_tool", traced("mortgage_tool", mortgage_node))
    g.add_node("compare_tool", traced("compare_tool", compare_node))
    g.add_node("smalltalk", traced("smalltalk", smalltalk_node))
    g.add_node("generate", traced("generate", generate_node))
    g.add_node("output_guard", traced("output_guard", output_guard_node))
    g.add_node("finalize", traced("finalize", finalize))

    g.add_edge(START, "input_guard")
    g.add_conditional_edges(
        "input_guard",
        lambda s: "finalize" if s["refused"] else "understand",
        {"finalize": "finalize", "understand": "understand"},
    )
    g.add_conditional_edges(
        "understand",
        route,
        {n: n for n in ("search", "mortgage_tool", "compare_tool", "smalltalk")},
    )
    for n in ("search", "mortgage_tool", "compare_tool", "smalltalk"):
        g.add_edge(n, "generate")
    g.add_edge("generate", "output_guard")
    g.add_edge("output_guard", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


async def run_chat_turn(
    deps: AgentDeps, session_id: str, message: str, context_ids: Sequence[str] = ()
) -> ChatResult:
    """Run one chat turn inside a single Langfuse trace (spans per node)."""
    graph = build_graph(deps)
    session = await deps.store.load(session_id)
    if context_ids and deps.hits_fetcher is not None:
        hits = await deps.hits_fetcher(list(context_ids))
        if hits:
            session.last_results = [h.model_copy(update={"listing_card": None}) for h in hits]
    with deps.tracer.trace("chat", session_id=session_id, input={"message": message[:500]}) as tr:
        state = await graph.ainvoke({"message": message, "session": session})
        guard = state.get("guard")
        cats = [guard.category] if guard and guard.category else []
        result = ChatResult(
            session_id=session_id,
            text=state["final"],
            shown=state.get("shown", []),
            intent=state.get("intent", "search"),
            llm_calls=deps.llm.calls,
            refused=bool(state.get("refused")),
            degraded=bool(state.get("degraded")),
            guard_categories=cats + state.get("output_flags", []),
            trace_id=tr.trace_id,
            trace_url=tr.url,
        )
        tr.update(
            output={
                "text": result.text[:500],
                "intent": result.intent,
                "llm_calls": result.llm_calls,
            }
        )
    await asyncio.to_thread(deps.tracer.flush)
    return result
