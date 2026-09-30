from typing import Literal

from pydantic import BaseModel, Field

PropertyType = Literal[
    "Single Family", "Condo", "Townhouse", "Manufactured", "Multi-Family", "Apartment", "Land"
]
FilterName = Literal[
    "city", "state", "price_min", "price_max", "beds_min", "baths_min", "sqft_min", "property_type"
]


class Filters(BaseModel):
    city: str | None = None
    state: str | None = Field(default=None, description="2-letter US state code")
    price_min: int | None = None
    price_max: int | None = None
    beds_min: float | None = None
    baths_min: float | None = None
    sqft_min: int | None = None
    property_type: PropertyType | None = None

    def active(self) -> dict[str, object]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ParsedQuery(BaseModel):
    """What the LLM extracts from ONE user message."""

    filters: Filters = Field(
        default_factory=Filters,
        description="Only constraints stated or changed in this message; others stay null.",
    )
    clear_fields: list[FilterName] = Field(
        default_factory=list,
        description="Filters the user explicitly removes, e.g. 'no price limit'.",
    )
    new_search: bool = Field(
        default=False, description="True if the user starts an unrelated new search."
    )
    semantic_query: str = Field(
        default="", description="Free-text preferences for semantic search (style, features)."
    )


class Hit(BaseModel):
    id: str
    address: str
    city: str
    state: str
    zip: str | None = None
    lat: float | None = None
    lng: float | None = None
    price: int | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: int | None = None
    year_built: int | None = None
    property_type: str | None = None
    hoa_fee: float | None = None
    listing_card: str | None = None


class RankedHit(BaseModel):
    hit: Hit
    score: float


class SearchResult(BaseModel):
    results: list[RankedHit]
    requested_filters: Filters
    applied_filters: Filters
    semantic_query: str
    relaxations: list[str] = Field(default_factory=list)
    message: str = ""
    n_vector: int = 0
    n_keyword: int = 0
