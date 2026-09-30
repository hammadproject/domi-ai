"""Grounded answer generation for search results (LLM call #2 of the turn)."""

import json

from pydantic import BaseModel

from app.llm.gemini import LLMClient
from app.rag.models import Hit, RankedHit


class GroundedAnswer(BaseModel):
    answer: str
    listing_ids: list[str]


SYSTEM = """You are Domi, a US home-search assistant. Answer the user's request using ONLY the
listing records provided. Rules:
- Every claim must come from a field in a record. If a field is null, say it isn't listed.
  Never invent features, conditions, neighborhood details or prices.
- Refer to listings by their number (#1, #2, ...) and address, in the order given.
- Do NOT describe neighborhoods, schools, safety, or who a home suits. Stay with objective
  facts: price, beds, baths, sqft, year built, property type, HOA.
- If the note is non-empty it says filters were relaxed: tell the user exactly that.
  If the note is empty, say nothing about filters.
- Be concise (under 150 words). No mortgage math; offer to estimate payments instead.
Return JSON: answer, and listing_ids = ids of the listings your answer mentions."""


def _record(rank: int, h: Hit) -> dict:
    return {
        "number": rank,
        "id": h.id,
        "address": h.address,
        "price": h.price,
        "beds": h.beds,
        "baths": h.baths,
        "sqft": h.sqft,
        "year_built": h.year_built,
        "property_type": h.property_type,
        "hoa_fee_monthly": h.hoa_fee,
    }


def generate_grounded(
    user_message: str, note: str, ranked: list[RankedHit], llm: LLMClient
) -> GroundedAnswer:
    records = [_record(i, r.hit) for i, r in enumerate(ranked, 1)]
    prompt = (
        f"User request: {user_message}\nNote: {note or '(empty)'}\n"
        f"Listing records:\n{json.dumps(records, indent=1)}"
    )
    return llm.generate_structured(prompt, GroundedAnswer, system=SYSTEM)


def validate_ids(answer: GroundedAnswer, ranked: list[RankedHit]) -> list[str]:
    """Keep only ids that were actually retrieved, preserving rank order."""
    allowed = {r.hit.id for r in ranked}
    mentioned = {i for i in answer.listing_ids if i in allowed}
    return [r.hit.id for r in ranked if r.hit.id in mentioned]
