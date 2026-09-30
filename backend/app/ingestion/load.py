from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.normalize import ListingRow
from app.models import Listing

_UPDATE_COLS = [
    "address", "city", "state", "zip", "lat", "lng", "price", "beds", "baths", "sqft",
    "lot_size", "year_built", "property_type", "hoa_fee", "description", "features",
    "listing_card", "embedding", "raw",
]  # fmt: skip


async def upsert_listings(
    session: AsyncSession, rows: Sequence[ListingRow], embeddings: Sequence[list[float]]
) -> int:
    """Idempotent upsert keyed on listing id."""
    if not rows:
        return 0
    values = [{**r.model_dump(), "embedding": e} for r, e in zip(rows, embeddings, strict=True)]
    stmt = insert(Listing).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Listing.id],
        set_={c: getattr(stmt.excluded, c) for c in _UPDATE_COLS} | {"updated_at": func.now()},
    )
    await session.execute(stmt)
    await session.commit()
    return len(values)
