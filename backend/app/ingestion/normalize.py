"""RentCast raw listing -> listings-table row (plan 4.2) + listing_card (plan 4.3)."""

from typing import Any

from pydantic import BaseModel


class ListingRow(BaseModel):
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
    lot_size: int | None = None
    year_built: int | None = None
    property_type: str | None = None
    hoa_fee: float | None = None
    description: str | None = None
    features: dict[str, Any] | None = None
    listing_card: str
    raw: dict[str, Any]


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(round(n)) if n is not None else None


def _hoa(v: Any) -> float | None:
    if isinstance(v, dict):
        return _num(v.get("fee"))
    return _num(v)


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# Personal contact data we never need to store.
_PII_KEYS = ("listingAgent", "listingOffice")

_TYPE_NOUN = {
    "single family": "house",
    "condo": "condo",
    "townhouse": "townhouse",
    "manufactured": "manufactured home",
    "multi-family": "multi-family home",
    "apartment": "apartment",
    "land": "lot",
}


def _fmt_count(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def build_listing_card(row: dict[str, Any]) -> str:
    """One natural-language string per listing. Only states fields that exist."""
    parts: list[str] = []
    if row["beds"] is not None:
        parts.append(f"{_fmt_count(row['beds'])} bed")
    if row["baths"] is not None:
        parts.append(f"{_fmt_count(row['baths'])} bath")
    noun = _TYPE_NOUN.get((row["property_type"] or "").lower(), "home")
    where = f"{row['city']} {row['state']}" + (f" {row['zip']}" if row["zip"] else "")
    head = ", ".join(parts)
    text = f"{head} {noun} in {where}" if head else f"{noun.capitalize()} in {where}"
    if row["price"] is not None:
        text += f", ${row['price']:,}"
    if row["sqft"] is not None:
        text += f", {row['sqft']:,} sqft"
    if row["year_built"] is not None:
        text += f", built {row['year_built']}"
    if row["hoa_fee"]:
        text += f", HOA ${row['hoa_fee']:,.0f}/mo"
    text += "."
    if row["description"]:
        text += f" {row['description']}"
    return text


def normalize_listing(raw: dict[str, Any]) -> ListingRow | None:
    """Return None for records without an id or a city/state (unusable)."""
    listing_id = _clean(raw.get("id"))
    city, state = _clean(raw.get("city")), _clean(raw.get("state"))
    if not listing_id or not city or not state:
        return None
    features = raw.get("features")
    row: dict[str, Any] = {
        "id": listing_id,
        "address": _clean(raw.get("formattedAddress")) or _clean(raw.get("addressLine1")) or "",
        "city": city,
        "state": state.upper(),
        "zip": _clean(raw.get("zipCode")),
        "lat": _num(raw.get("latitude")),
        "lng": _num(raw.get("longitude")),
        "price": _int(raw.get("price")),
        "beds": _num(raw.get("bedrooms")),
        "baths": _num(raw.get("bathrooms")),
        "sqft": _int(raw.get("squareFootage")),
        "lot_size": _int(raw.get("lotSize")),
        "year_built": _int(raw.get("yearBuilt")),
        "property_type": _clean(raw.get("propertyType")),
        "hoa_fee": _hoa(raw.get("hoa")),
        "description": _clean(raw.get("description")),
        "features": features if isinstance(features, dict) and features else None,
    }
    return ListingRow(
        **row,
        listing_card=build_listing_card(row),
        raw={k: v for k, v in raw.items() if k not in _PII_KEYS},
    )
