from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    price: Mapped[int | None] = mapped_column(Integer)
    beds: Mapped[float | None] = mapped_column(Float)
    baths: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer)
    lot_size: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String)
    hoa_fee: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    listing_card: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(listing_card, '') || ' ' "
            "|| coalesce(description, '') || ' ' || coalesce(address, ''))",
            persisted=True,
        ),
    )
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_listings_city_price_beds", "city", "price", "beds"),
        Index("ix_listings_tsv", "tsv", postgresql_using="gin"),
    )
