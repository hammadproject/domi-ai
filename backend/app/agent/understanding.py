"""The ONE routing + query-understanding LLM call per turn (plan 5.0)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.agent.memory import SessionState
from app.llm.gemini import LLMClient
from app.rag.models import ParsedQuery

Intent = Literal["search", "mortgage", "compare", "smalltalk"]


class MortgageArgs(BaseModel):
    kind: Literal["payment", "scenarios", "term_compare", "affordability"] = "payment"
    price: float | None = Field(default=None, description="Home price if the user gave one")
    down_payment: float | None = Field(default=None, description="Dollar amount")
    down_payment_pct: float | None = Field(default=None, description="Percent, e.g. 10 for 10%")
    term_years: int | None = None
    hoa_monthly: float | None = None
    annual_income: float | None = None
    monthly_debts: float | None = None
    interest_rate: float | None = Field(default=None, description="Annual percent if stated")


class TurnUnderstanding(ParsedQuery):
    intent: Intent = "search"
    mortgage: MortgageArgs = Field(default_factory=MortgageArgs)
    listing_positions: list[int] = Field(
        default_factory=list,
        description="1-based positions in the previously shown list the user refers to",
    )


SYSTEM = """You are the routing and understanding step of a US home-search assistant.
Return JSON for ONE user message.

intent:
- search: looking for / refining a home search (beds, price, city, features). Follow-ups like
  "make it 550k" or "add a pool" are search.
- mortgage: monthly payment, down payment, PMI, affordability, 15 vs 30 year, "how much house
  can I afford". Not a search, even if it refers to a listing.
- compare: compare two or three previously shown listings.
- smalltalk: greetings, thanks, what can you do, anything unrelated to homes.

Search fields (same rules as always): fill `filters` ONLY with constraints stated or changed in
THIS message; "3 bed" means beds_min=3; "500k"=500000; state is a 2-letter code;
property_type one of Single Family, Condo, Townhouse, Manufactured, Multi-Family, Apartment,
Land ("house"/"home" -> Single Family). Explicitly removed constraints go in `clear_fields`.
new_search=true only for an unrelated new search. `semantic_query` is short free text of style
or feature preferences; never add demographic or neighborhood-quality claims.

listing_positions: if the user refers to listings already shown ("the first one", "#2", "the
first two", "compare them", "all of them"), give their 1-based positions from the list below.
Empty otherwise.

mortgage: fill only what the user stated. For "payment" on a shown listing leave price null and
set listing_positions. kind: payment | scenarios (different down payments) | term_compare
(15 vs 30 year) | affordability (how much can I afford; needs income).
Return JSON only."""


def build_prompt(message: str, session: SessionState) -> str:
    shown = "\n".join(
        f"{i}. {h.address} - ${h.price:,}" if h.price else f"{i}. {h.address}"
        for i, h in enumerate(session.last_results, 1)
    )
    recent = " | ".join(t.content[:120] for t in session.history if t.role == "user")[-300:]
    return (
        f"Current search filters: {session.filters.active()}\n"
        f"Previously shown listings:\n{shown or '(none)'}\n"
        f"Earlier user messages: {recent or '(none)'}\n"
        f"User message: {message}"
    )


def understand(message: str, session: SessionState, llm: LLMClient) -> TurnUnderstanding:
    return llm.generate_structured(build_prompt(message, session), TurnUnderstanding, system=SYSTEM)
