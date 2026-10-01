"""Grounded answer generation for search results (LLM call #2 of the turn).

The app shows every home as a card next to the answer, so the text is deliberately short:
a one-sentence lead-in plus a few bullet points about the set. It must not re-list the homes.
"""

import json

from pydantic import BaseModel, Field

from app.llm.gemini import LLMClient
from app.rag.models import Hit, RankedHit


class GroundedAnswer(BaseModel):
    answer: str = Field(description="ONE short lead-in sentence (max 25 words). Do not list homes.")
    bullets: list[str] = Field(
        default_factory=list,
        description="0 to 4 short facts about the set (max 14 words each).",
    )
    listing_ids: list[str]


SYSTEM = """You are Domi, a US home-search assistant. Answer using ONLY the listing records
provided. The app displays every home as a card right below your answer, so do NOT list or
describe the homes one by one.

Return JSON with:
- answer: ONE short lead-in sentence (max 25 words): how many homes, and for what request.
  If the note is non-empty, filters were relaxed: say exactly what was relaxed in this sentence.
- bullets: 0 to 4 short bullet points (max 14 words each, no leading dash) giving useful facts
  about the set as a whole, for example: what they all share, the price range (lowest to
  highest), the size range, or a field missing for every home (say "HOA not listed").
  Only facts you can read from the records. No advice, no opinions.
- listing_ids: ids of the homes your answer is about.

Rules: every claim must come from a field in a record. Never invent features, conditions or
prices. Do NOT describe neighborhoods, schools, safety, or who a home suits. Do no mortgage
math; if useful, one bullet may offer to estimate payments."""


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


def render(answer: GroundedAnswer) -> str:
    """Lead-in sentence, then bullets on their own lines ('- ' prefix), as the UI expects."""
    bullets = [b.strip().lstrip("-• ").strip() for b in answer.bullets if b.strip()][:4]
    text = answer.answer.strip()
    if bullets:
        text += "\n" + "\n".join(f"- {b}" for b in bullets)
    return text


def validate_ids(answer: GroundedAnswer, ranked: list[RankedHit]) -> list[str]:
    """Keep only ids that were actually retrieved, preserving rank order."""
    allowed = {r.hit.id for r in ranked}
    mentioned = {i for i in answer.listing_ids if i in allowed}
    return [r.hit.id for r in ranked if r.hit.id in mentioned]
