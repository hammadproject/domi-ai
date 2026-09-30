"""GET /api/cities: real per-city stats for the landing page (Redis-cached)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_cache
from app.cache import Cache, make_key
from app.config import get_settings
from app.db import get_session
from app.models import Listing
from app.ratelimit import limit_api

router = APIRouter(dependencies=[Depends(limit_api)])


class CityStats(BaseModel):
    city: str
    state: str
    listing_count: int
    median_price: int | None
    min_price: int | None
    max_price: int | None
    center_lat: float | None
    center_lng: float | None


@router.get("/api/cities", response_model=list[CityStats])
async def cities(
    db: AsyncSession = Depends(get_session), cache: Cache = Depends(get_cache)
) -> list[dict]:
    key = make_key("cities")
    if (cached := await cache.get(key)) is not None:
        return cached
    rows = (
        await db.execute(
            select(
                Listing.city,
                Listing.state,
                func.count().label("listing_count"),
                func.percentile_cont(0.5).within_group(Listing.price).label("median_price"),
                func.min(Listing.price).label("min_price"),
                func.max(Listing.price).label("max_price"),
                func.avg(Listing.lat).label("center_lat"),
                func.avg(Listing.lng).label("center_lng"),
            )
            # homes only: vacant land is hidden from home searches everywhere else too
            .where(or_(Listing.property_type.is_(None), Listing.property_type != "Land"))
            .group_by(Listing.city, Listing.state)
            .order_by(Listing.city)
        )
    ).all()
    body = [
        CityStats(
            city=r.city,
            state=r.state,
            listing_count=r.listing_count,
            median_price=round(r.median_price) if r.median_price is not None else None,
            min_price=r.min_price,
            max_price=r.max_price,
            center_lat=float(r.center_lat) if r.center_lat is not None else None,
            center_lng=float(r.center_lng) if r.center_lng is not None else None,
        ).model_dump()
        for r in rows
    ]
    await cache.set(key, body, get_settings().cache_ttl_seconds)
    return body
