import asyncio
import selectors

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.models import Filters, Hit, ParsedQuery
from app.rag.pipeline import relaxation_steps, search
from app.rag.query_parser import merge_filters
from app.rag.rerank import rerank
from app.rag.retrieval import filter_clauses, keyword_terms


def hit(i: str, price: int = 100) -> Hit:
    return Hit(id=i, address=f"{i} St", city="Austin", state="TX", price=price, listing_card=i)


def test_rrf_rewards_agreement_between_lists() -> None:
    fused = reciprocal_rank_fusion([[hit("a"), hit("b"), hit("c")], [hit("c"), hit("b")]])
    ids = [h.id for h, _ in fused]
    assert ids[0] in {"b", "c"} and set(ids) == {"a", "b", "c"}
    assert ids.index("a") == 2  # only in one list, rank 1 < b (ranks 2,2) and c (3,1)


def test_rerank_orders_by_score_and_limits() -> None:
    cands = [(hit(x), 0.0) for x in "abcdefg"]
    out = rerank("q", cands, top_k=3, score_fn=lambda q, docs: [ord(d[0]) for d in docs])
    assert [r.hit.id for r in out] == ["g", "f", "e"]
    assert rerank("q", [], score_fn=lambda q, d: []) == []


def test_keyword_terms_drop_stopwords_and_short_tokens() -> None:
    assert keyword_terms("a modern home with pool near 78704!") == ["modern", "pool", "78704"]


def test_merge_followup_changes_only_what_was_said() -> None:
    prior = Filters(city="Austin", state="TX", price_max=500000, beds_min=3)
    parsed = ParsedQuery(filters=Filters(price_max=550000))
    merged = merge_filters(prior, parsed)
    assert (merged.price_max, merged.city, merged.beds_min) == (550000, "Austin", 3)
    assert prior.price_max == 500000  # prior not mutated


def test_merge_clear_and_new_search() -> None:
    prior = Filters(city="Austin", price_max=500000)
    cleared = merge_filters(prior, ParsedQuery(clear_fields=["price_max"]))
    assert cleared.price_max is None and cleared.city == "Austin"
    fresh = merge_filters(prior, ParsedQuery(filters=Filters(city="Dallas"), new_search=True))
    assert fresh.city == "Dallas" and fresh.price_max is None


def test_relaxation_order_is_cumulative_and_one_filter_at_a_time() -> None:
    f = Filters(city="Austin", price_max=500000, beds_min=3, sqft_min=2000, property_type="Condo")
    steps = relaxation_steps(f)
    assert [d.split()[0] for d, _ in steps] == ["raised", "lowered", "dropped", "dropped"]
    assert steps[0][1].price_max == 550000
    assert steps[1][1].beds_min == 2 and steps[1][1].price_max == 550000
    assert steps[-1][1].property_type is None and steps[-1][1].city == "Austin"


def test_relaxation_single_bedroom_minimum_is_removed() -> None:
    (desc, relaxed), *_ = relaxation_steps(Filters(beds_min=1))
    assert relaxed.beds_min is None and "removed" in desc


def test_land_excluded_by_default_only() -> None:
    default_sql = " ".join(str(c) for c in filter_clauses(Filters()))
    land_sql = " ".join(str(c) for c in filter_clauses(Filters(property_type="Land")))
    assert "property_type !=" in default_sql
    assert "property_type !=" not in land_sql and "property_type =" in land_sql


class FakeLLM:
    def __init__(self, parsed: ParsedQuery) -> None:
        self.parsed, self.calls = parsed, 0

    def generate_structured(self, prompt, schema, *, system=None):
        self.calls += 1
        return self.parsed


async def test_search_uses_one_llm_call_and_no_fallback_when_results_exist() -> None:
    llm = FakeLLM(ParsedQuery(filters=Filters(city="Austin"), semantic_query="modern"))

    async def retriever(f, q):
        return [hit("a"), hit("b")], [hit("b")]

    res = await search("x", retriever=retriever, llm=llm, score_fn=lambda q, d: [1.0] * len(d))
    assert llm.calls == 1 and not res.relaxations
    assert {r.hit.id for r in res.results} == {"a", "b"}


async def test_search_fallback_relaxes_until_results_and_reports_it() -> None:
    llm = FakeLLM(ParsedQuery(filters=Filters(city="Austin", price_max=400000, beds_min=4)))
    seen: list[Filters] = []

    async def retriever(f, q):
        seen.append(f)
        return ([hit("z")], []) if f.beds_min == 3 else ([], [])

    res = await search("x", retriever=retriever, llm=llm, score_fn=lambda q, d: [1.0] * len(d))
    assert [r.hit.id for r in res.results] == ["z"]
    assert len(res.relaxations) == 2
    assert res.applied_filters.price_max == 440000 and res.applied_filters.beds_min == 3
    assert res.requested_filters.beds_min == 4  # original request preserved
    assert "raised max price" in res.message and "lowered minimum bedrooms" in res.message


async def test_search_honest_when_nothing_matches() -> None:
    llm = FakeLLM(ParsedQuery(filters=Filters(city="Nowhere", price_max=1)))

    async def retriever(f, q):
        return [], []

    res = await search("x", retriever=retriever, llm=llm, score_fn=lambda q, d: [])
    assert res.results == [] and res.message.startswith("No listings match")


# ---- read-only checks against the real database (skipped without DATABASE_URL) ----
needs_db = pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set")


def _with_session(coro_fn):
    from app.db import get_engine, get_session

    async def runner():
        try:
            async for session in get_session():
                return await coro_fn(session)
        finally:
            await get_engine().dispose()

    return asyncio.run(
        runner(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    )


@needs_db
def test_db_filters_are_strictly_respected_in_both_searches() -> None:
    from app.models import Listing
    from app.rag.retrieval import keyword_search, vector_search

    f = Filters(city="Austin", state="TX", price_max=500000, beds_min=3, baths_min=2)

    async def check(session):
        # reuse a stored embedding as the query vector so no API call is needed
        qvec = (
            (await session.execute(select(Listing.embedding).where(Listing.embedding.is_not(None))))
            .scalars()
            .first()
        )
        vec = await vector_search(session, f, list(qvec))
        kw = await keyword_search(session, f, "townhouse house austin")
        return vec, kw

    vec, kw = _with_session(check)
    assert vec and kw
    for h in vec + kw:
        assert h.city == "Austin" and h.price <= 500000 and h.beds >= 3 and h.baths >= 2
        assert h.property_type != "Land"


@needs_db
def test_db_land_only_returned_when_requested() -> None:
    from app.rag.retrieval import keyword_search

    async def check(session):
        default = await keyword_search(session, Filters(city="Dallas"), "land lot dallas")
        land = await keyword_search(
            session, Filters(city="Dallas", property_type="Land"), "land lot dallas"
        )
        n = (await session.execute(text("select count(*) from listings"))).scalar()
        return default, land, n

    default, land, n = _with_session(check)
    assert n >= 300
    assert all(h.property_type != "Land" for h in default)
    assert land and all(h.property_type == "Land" for h in land)
