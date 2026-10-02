"""GET /api/listings (filters, pagination, sort) and GET /api/listings/{id}. Redis-cached."""

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_cache
from app.cache import Cache, make_key
from app.config import get_settings
from app.db import get_session
from app.models import Listing
from app.rag.models import Filters, Hit, PropertyType
from app.rag.retrieval import HIT_COLUMNS, filter_clauses
from app.ratelimit import limit_api

router = APIRouter(dependencies=[Depends(limit_api)])

SortKey = Literal["price_asc", "price_desc", "newest", "sqft_desc"]
_ORDER = {
    "price_asc": (Listing.price.asc().nulls_last(),),
    "price_desc": (Listing.price.desc().nulls_last(),),
    "newest": (Listing.year_built.desc().nulls_last(),),
    "sqft_desc": (Listing.sqft.desc().nulls_last(),),
}


@router.get("/api/listings")
async def list_listings(
    city: str | None = Query(None, min_length=1, max_length=60),
    state: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    price_min: int | None = Query(None, ge=0, le=1_000_000_000),
    price_max: int | None = Query(None, ge=0, le=1_000_000_000),
    beds_min: float | None = Query(None, ge=0, le=20),
    baths_min: float | None = Query(None, ge=0, le=20),
    sqft_min: int | None = Query(None, ge=0, le=100_000),
    property_type: PropertyType | None = None,
    sort: SortKey = "price_asc",
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=250),
    db: AsyncSession = Depends(get_session),
    cache: Cache = Depends(get_cache),
) -> dict:
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=422, detail="price_min cannot be greater than price_max")

    filters = Filters(
        city=city, state=state, price_min=price_min, price_max=price_max, beds_min=beds_min,
        baths_min=baths_min, sqft_min=sqft_min, property_type=property_type,
    )  # fmt: skip
    key = make_key("listings", filters.model_dump(), sort, page, page_size)
    if (cached := await cache.get(key)) is not None:
        return cached

    clauses = filter_clauses(filters)  # Land excluded unless property_type=Land
    total = (await db.execute(select(func.count()).select_from(Listing).where(*clauses))).scalar()
    rows = (
        await db.execute(
            select(*HIT_COLUMNS)
            .where(*clauses)
            .order_by(*_ORDER[sort], Listing.id)  # id breaks ties: stable pages
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    body = {
        "items": [Hit(**dict(r._mapping)).model_dump(exclude={"listing_card"}) for r in rows],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil((total or 0) / page_size),
    }
    await cache.set(key, body, get_settings().cache_ttl_seconds)
    return body


@router.get("/api/listings/{listing_id}")
async def get_listing(
    listing_id: str = Path(min_length=1, max_length=200),
    db: AsyncSession = Depends(get_session),
    cache: Cache = Depends(get_cache),
) -> dict:
    key = make_key("listing", listing_id)
    if (cached := await cache.get(key)) is not None:
        return cached
    row = (
        await db.execute(
            select(*HIT_COLUMNS, Listing.lot_size, Listing.description, Listing.features).where(
                Listing.id == listing_id
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    body = {k: v for k, v in row._mapping.items() if k != "listing_card"}
    await cache.set(key, body, get_settings().cache_ttl_seconds)
    return body
