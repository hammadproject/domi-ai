"""POST /api/compare: 2-3 listings side by side (deterministic tool, no LLM)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mortgage import AssumptionOverrides
from app.db import get_session
from app.rag.retrieval import get_hits
from app.ratelimit import limit_api
from app.tools.compare import Comparison, compare_listings

router = APIRouter(dependencies=[Depends(limit_api)])

ListingId = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class CompareRequest(AssumptionOverrides):
    listing_ids: list[ListingId] = Field(min_length=2, max_length=3)
    down_payment_pct: float = Field(default=20.0, ge=0, le=100)
    term_years: int = Field(default=30, ge=1, le=50)


@router.post("/api/compare", response_model=Comparison)
async def compare(req: CompareRequest, db: AsyncSession = Depends(get_session)) -> Comparison:
    if len(set(req.listing_ids)) != len(req.listing_ids):
        raise HTTPException(status_code=422, detail="listing_ids must be distinct")
    hits = await get_hits(db, req.listing_ids)
    if len(hits) != len(req.listing_ids):
        found = {h.id for h in hits}
        missing = [i for i in req.listing_ids if i not in found]
        raise HTTPException(status_code=404, detail=f"Listing not found: {missing[0]}")
    return compare_listings(
        hits,
        down_payment_pct=req.down_payment_pct,
        term_years=req.term_years,
        assumptions=req.assumptions(),
    )
