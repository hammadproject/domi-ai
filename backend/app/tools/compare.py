"""Side-by-side comparison of 2-3 listings. Pros/cons are derived from fields only:
each statement is a relative fact about the compared set, never a neighborhood opinion."""

from collections.abc import Callable, Sequence

from pydantic import BaseModel

from app.rag.models import Hit
from app.tools.mortgage import DISCLAIMER, MortgageAssumptions, estimate_payment


class ListingComparison(BaseModel):
    id: str
    address: str
    city: str
    state: str
    zip: str | None
    property_type: str | None
    lat: float | None
    lng: float | None
    price: int | None
    price_per_sqft: float | None
    beds: float | None
    baths: float | None
    sqft: int | None
    year_built: int | None
    hoa_fee: float | None
    est_monthly_payment: float | None
    pros: list[str]
    cons: list[str]
    missing_fields: list[str]


class Comparison(BaseModel):
    listings: list[ListingComparison]
    down_payment_pct: float
    term_years: int
    payment_note: str


def _money(n: float) -> str:
    return f"${n:,.0f}"


def _metrics(
    h: Hit, a: MortgageAssumptions, down_pct: float, term_years: int
) -> dict[str, float | None]:
    ppsf = round(h.price / h.sqft, 2) if h.price and h.sqft else None
    monthly = None
    if h.price:
        monthly = estimate_payment(
            h.price,
            down_payment_pct=down_pct,
            hoa_monthly=h.hoa_fee or 0.0,
            term_years=term_years,
            assumptions=a,
        ).total_monthly
    return {
        "price": h.price,
        "ppsf": ppsf,
        "sqft": h.sqft,
        "year": h.year_built,
        "beds": h.beds,
        "baths": h.baths,
        "hoa": h.hoa_fee,  # None = not listed; never treated as "no HOA" in pros/cons
        "monthly": monthly,
    }


# (key, pro text when best, con text when worst, lower-is-better, formatter)
_RULES: list[tuple[str, str, str, bool, Callable[[float], str]]] = [
    ("price", "Lowest list price", "Highest list price", True, _money),
    ("ppsf", "Lowest price per sqft", "Highest price per sqft", True, lambda v: f"${v:,.0f}/sqft"),
    ("sqft", "Most living space", "Least living space", False, lambda v: f"{v:,.0f} sqft"),
    ("beds", "Most bedrooms", "Fewest bedrooms", False, lambda v: f"{v:g} bd"),
    ("baths", "Most bathrooms", "Fewest bathrooms", False, lambda v: f"{v:g} ba"),
    ("year", "Newest build", "Oldest build", False, lambda v: f"built {v:.0f}"),
    ("hoa", "Lowest HOA fee", "Highest HOA fee", True, lambda v: f"HOA ${v:,.0f}/mo"),
    ("monthly", "Lowest est. monthly payment", "Highest est. monthly payment", True, _money),
]  # fmt: skip


def compare_listings(
    listings: Sequence[Hit],
    *,
    down_payment_pct: float = 20.0,
    term_years: int = 30,
    assumptions: MortgageAssumptions | None = None,
) -> Comparison:
    if not 2 <= len(listings) <= 3:
        raise ValueError("compare 2 or 3 listings")
    a = assumptions or MortgageAssumptions.from_settings()
    metrics = [_metrics(h, a, down_payment_pct, term_years) for h in listings]
    pros: list[list[str]] = [[] for _ in listings]
    cons: list[list[str]] = [[] for _ in listings]

    for key, pro_text, con_text, lower_better, fmt in _RULES:
        vals = [(i, m[key]) for i, m in enumerate(metrics) if m[key] is not None]
        if len(vals) < 2:
            continue  # need at least two known values to say anything relative
        nums = [v for _, v in vals]
        if len(set(nums)) == 1:
            continue  # all equal: no pro or con
        best = min(nums) if lower_better else max(nums)
        worst = max(nums) if lower_better else min(nums)
        for i, v in vals:
            if v == best:
                pros[i].append(f"{pro_text} ({fmt(v)})")
            elif v == worst:
                cons[i].append(f"{con_text} ({fmt(v)})")

    out = []
    for h, m, p, c in zip(listings, metrics, pros, cons, strict=True):
        missing = [
            name
            for name, val in (
                ("price", h.price), ("beds", h.beds), ("baths", h.baths),
                ("sqft", h.sqft), ("year_built", h.year_built),
            )
            if val is None
        ]  # fmt: skip
        out.append(
            ListingComparison(
                id=h.id,
                address=h.address,
                city=h.city,
                state=h.state,
                zip=h.zip,
                property_type=h.property_type,
                lat=h.lat,
                lng=h.lng,
                price=h.price,
                price_per_sqft=m["ppsf"],
                beds=h.beds,
                baths=h.baths,
                sqft=h.sqft,
                year_built=h.year_built,
                hoa_fee=h.hoa_fee,
                est_monthly_payment=m["monthly"],
                pros=p,
                cons=c,
                missing_fields=missing,
            )
        )
    note = (
        f"Monthly payment assumes {down_payment_pct:g}% down, a {term_years}-year loan and $0 HOA "
        f"where no fee is listed. "
        f"{DISCLAIMER}"
    )
    return Comparison(
        listings=out, down_payment_pct=down_payment_pct, term_years=term_years, payment_note=note
    )
