"""Query understanding: ONE structured LLM call per turn -> filters + semantic query."""

from app.llm.gemini import GeminiClient, LLMClient
from app.rag.models import Filters, ParsedQuery

SYSTEM = """You extract home-search constraints from a user message for a US listings database.
Cities available: Austin TX, Dallas TX, Phoenix AZ.
Rules:
- Fill `filters` ONLY with constraints stated or changed in THIS message. Leave the rest null.
  "3 bed" or "3 bedrooms" means beds_min=3. "under 500k" means price_max=500000.
  "make it 550k" / "raise my budget to 550k" after a price limit means price_max=550000.
- Expand abbreviations: "500k"=500000, "1.2m"=1200000. State is a 2-letter code.
- property_type must be one of: Single Family, Condo, Townhouse, Manufactured, Multi-Family,
  Apartment, Land. Map "house"/"home" to Single Family; only use Land if asked for land/lots.
- Put explicitly removed constraints in `clear_fields` (e.g. "no price limit" -> price_max).
- Set new_search=true only if the user starts an unrelated search (e.g. switches topic entirely).
- `semantic_query`: short free-text of style/feature/location preferences (e.g. "modern
  townhouse near downtown"). Empty string if there are none. Never add demographic or
  neighborhood-quality claims.
Return JSON only."""


def merge_filters(prior: Filters | None, parsed: ParsedQuery) -> Filters:
    """Apply a parsed turn on top of the session's prior filters."""
    base = Filters() if parsed.new_search or prior is None else prior.model_copy()
    for name in parsed.clear_fields:
        setattr(base, name, None)
    updates = {k: v for k, v in parsed.filters.model_dump().items() if v is not None}
    if updates.get("state"):
        updates["state"] = str(updates["state"]).upper()
    return base.model_copy(update=updates)


def parse_query(
    message: str, prior: Filters | None = None, llm: LLMClient | None = None
) -> tuple[Filters, ParsedQuery]:
    llm = llm or GeminiClient()
    current = prior.active() if prior else {}
    prompt = f"Current filters: {current}\nUser message: {message}"
    parsed = llm.generate_structured(prompt, ParsedQuery, system=SYSTEM)
    return merge_filters(prior, parsed), parsed
