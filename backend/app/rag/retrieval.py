"""Metadata pre-filter + vector search + keyword search (all on the filtered set)."""

import re

from sqlalchemy import Select, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing
from app.rag.models import Filters, Hit

TOP_N = 30
_COLS = (
    Listing.id, Listing.address, Listing.city, Listing.state, Listing.zip, Listing.lat,
    Listing.lng, Listing.price, Listing.beds, Listing.baths, Listing.sqft, Listing.year_built,
    Listing.property_type, Listing.hoa_fee, Listing.listing_card,
)  # fmt: skip
_STOPWORDS = {
    "the", "and", "for", "with", "near", "in", "a", "an", "of", "to", "or", "is", "are", "on",
    "at", "by", "some", "any", "that", "this", "home", "homes", "house", "houses", "bed",
    "beds", "bath", "baths",
}  # fmt: skip


def filter_clauses(f: Filters) -> list:
    """SQL conditions for the structured filters. Land is excluded unless asked for."""
    c = []
    if f.city:
        c.append(func.lower(Listing.city) == f.city.lower())
    if f.state:
        c.append(func.upper(Listing.state) == f.state.upper())
    if f.price_min is not None:
        c.append(Listing.price >= f.price_min)
    if f.price_max is not None:
        c.append(Listing.price <= f.price_max)
    if f.beds_min is not None:
        c.append(Listing.beds >= f.beds_min)
    if f.baths_min is not None:
        c.append(Listing.baths >= f.baths_min)
    if f.sqft_min is not None:
        c.append(Listing.sqft >= f.sqft_min)
    if f.property_type:
        c.append(Listing.property_type == f.property_type)
    else:
        c.append(or_(Listing.property_type.is_(None), Listing.property_type != "Land"))
    return c


def keyword_terms(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if len(tok) >= 3 and tok not in _STOPWORDS:
            seen[tok] = None
    return list(seen)


def _vector_stmt(f: Filters, qvec: list[float]) -> Select:
    return (
        select(*_COLS)
        .where(and_(*filter_clauses(f)), Listing.embedding.is_not(None))
        .order_by(Listing.embedding.cosine_distance(qvec))
        .limit(TOP_N)
    )


def _keyword_stmt(f: Filters, terms: list[str]) -> Select:
    tsq = func.to_tsquery("english", literal(" | ".join(terms)))
    return (
        select(*_COLS)
        .where(and_(*filter_clauses(f)), Listing.tsv.op("@@")(tsq))
        .order_by(func.ts_rank(Listing.tsv, tsq).desc())
        .limit(TOP_N)
    )


async def vector_search(session: AsyncSession, f: Filters, qvec: list[float]) -> list[Hit]:
    rows = (await session.execute(_vector_stmt(f, qvec))).all()
    return [Hit(**dict(r._mapping)) for r in rows]


async def keyword_search(session: AsyncSession, f: Filters, query: str) -> list[Hit]:
    terms = keyword_terms(query)
    if not terms:
        return []
    rows = (await session.execute(_keyword_stmt(f, terms))).all()
    return [Hit(**dict(r._mapping)) for r in rows]
