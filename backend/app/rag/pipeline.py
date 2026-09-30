"""Retrieval pipeline: parse -> pre-filter -> vector + keyword -> RRF -> rerank -> fallback."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embed import embed_query
from app.llm.gemini import LLMClient
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.models import Filters, Hit, RankedHit, SearchResult
from app.rag.query_parser import parse_query
from app.rag.rerank import ScoreFn, cross_encoder_scores, rerank
from app.rag.retrieval import keyword_search, vector_search

log = logging.getLogger(__name__)

# (filters, semantic_query) -> (vector hits, keyword hits); injectable for tests
Retriever = Callable[[Filters, str], Awaitable[tuple[list[Hit], list[Hit]]]]


def _usd(n: float | int) -> str:
    return f"${int(round(n)):,}"


def relaxation_steps(f: Filters) -> list[tuple[str, Filters]]:
    """Cumulative one-filter-at-a-time relaxations, in plan order (5.1 step 7)."""
    steps: list[tuple[str, Filters]] = []
    cur = f
    if cur.price_max is not None:
        new = int(round(cur.price_max * 1.10))
        desc = f"raised max price from {_usd(cur.price_max)} to {_usd(new)} (+10%)"
        cur = cur.model_copy(update={"price_max": new})
        steps.append((desc, cur))
    if cur.beds_min is not None:
        new_beds = cur.beds_min - 1
        if new_beds >= 1:
            desc = f"lowered minimum bedrooms from {cur.beds_min:g} to {new_beds:g}"
        else:
            new_beds, desc = None, f"removed the {cur.beds_min:g}-bedroom minimum"
        cur = cur.model_copy(update={"beds_min": new_beds})
        steps.append((desc, cur))
    for field, label in (
        ("sqft_min", "minimum square footage"),
        ("baths_min", "minimum bathrooms"),
        ("property_type", "property type"),
    ):
        if getattr(cur, field) is not None:
            cur = cur.model_copy(update={field: None})
            steps.append((f"dropped the {label} requirement", cur))
    return steps


def db_retriever(session: AsyncSession) -> Retriever:
    async def run(f: Filters, semantic_query: str) -> tuple[list[Hit], list[Hit]]:
        qvec = list(await asyncio.to_thread(embed_query, semantic_query))
        return (
            await vector_search(session, f, qvec),
            await keyword_search(session, f, semantic_query),
        )

    return run


async def _retrieve_ranked(
    retriever: Retriever, f: Filters, semantic_query: str, score_fn: ScoreFn, top_k: int
) -> tuple[list[RankedHit], int, int]:
    vec, kw = await retriever(f, semantic_query)
    fused = reciprocal_rank_fusion([vec, kw])
    ranked = rerank(semantic_query, fused, top_k=top_k, score_fn=score_fn)
    return ranked, len(vec), len(kw)


def _describe(f: Filters, semantic_query: str) -> str:
    """Text driving embedding, keywords and rerank. With no free-text preferences, use a
    plain-English summary of the filters so vector search still has a meaningful input."""
    if semantic_query.strip():
        return semantic_query.strip()
    bits = []
    if f.beds_min is not None:
        bits.append(f"{f.beds_min:g} bed")
    bits.append(f.property_type or "home")
    where = " ".join(x for x in (f.city, f.state) if x)
    return " ".join(bits) + (f" in {where}" if where else "")


async def search(
    message: str,
    *,
    retriever: Retriever,
    prior: Filters | None = None,
    llm: LLMClient | None = None,
    score_fn: ScoreFn = cross_encoder_scores,
    top_k: int = 5,
) -> SearchResult:
    """One chat-turn retrieval. Uses exactly one LLM call (the parse)."""
    requested, parsed = await asyncio.to_thread(parse_query, message, prior, llm)
    # The text that drives embedding, keywords and rerank. Fall back to a filter summary
    # when the user gave no free-text preferences, so vector search still has an input.
    query_text = _describe(requested, parsed.semantic_query)

    ranked, n_vec, n_kw = await _retrieve_ranked(retriever, requested, query_text, score_fn, top_k)
    applied, relaxations = requested, []

    if not ranked:
        for desc, relaxed in relaxation_steps(requested):
            ranked, n_vec, n_kw = await _retrieve_ranked(
                retriever, relaxed, query_text, score_fn, top_k
            )
            applied, relaxations = relaxed, relaxations + [desc]
            if ranked:
                break

    if not ranked:
        tried = f" (I also tried: {', then '.join(relaxations)})" if relaxations else ""
        message_out = f"No listings match those criteria{tried}."
    elif relaxations:
        message_out = (
            "No exact matches, so I "
            + ", then ".join(relaxations)
            + ". Showing the closest results."
        )
    else:
        message_out = f"Found {len(ranked)} matching listings."

    log.info(
        "search: filters=%s relaxed=%d results=%d", applied.active(), len(relaxations), len(ranked)
    )
    return SearchResult(
        results=ranked,
        requested_filters=requested,
        applied_filters=applied,
        semantic_query=query_text,
        relaxations=relaxations,
        message=message_out,
        n_vector=n_vec,
        n_keyword=n_kw,
    )
