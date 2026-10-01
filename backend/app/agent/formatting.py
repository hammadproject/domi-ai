"""Deterministic text for tool results and fallbacks. No LLM: every number comes from the
tools, so nothing can be invented or mis-calculated.

Format (rendered by the chat UI): a short lead line, then "- " bullets. In comparisons a "+ "
line is a plus and a "- " line a minus; "1. " lines head a home.
"""

from app.rag.models import Hit, RankedHit
from app.tools.compare import Comparison
from app.tools.mortgage import (
    DISCLAIMER,
    Affordability,
    PaymentBreakdown,
    TermComparison,
)

SMALLTALK_REPLY = (
    "Hi, I'm Domi. I can help you with:\n"
    "- Searching homes for sale in Austin TX, Dallas TX and Phoenix AZ\n"
    "- Estimating a monthly mortgage payment for a home\n"
    "- Working out how much house you can afford\n"
    "- Comparing two or three listings\n"
    "What would you like to do?"
)


def usd(n: float | None) -> str:
    return f"${n:,.0f}" if n is not None else "n/a"


def usd2(n: float) -> str:
    return f"${n:,.2f}"


def describe_hit(h: Hit) -> str:
    beds = f"{h.beds:g} bd" if h.beds is not None else "? bd"
    baths = f"{h.baths:g} ba" if h.baths is not None else "? ba"
    sqft = f"{h.sqft:,} sqft" if h.sqft else "sqft not listed"
    return f"{h.address} ({usd(h.price)}, {beds}/{baths}, {sqft})"


def search_fallback_text(message: str, ranked: list[RankedHit]) -> str:
    """Used when the generation call is skipped or fails, or nothing matched."""
    if not ranked:
        return message
    lines = [f"- #{i} {describe_hit(r.hit)}" for i, r in enumerate(ranked, 1)]
    return f"{message}\n" + "\n".join(lines)


def payment_text(b: PaymentBreakdown, label: str | None = None) -> str:
    lines = [
        f"Estimated monthly payment{f' for {label}' if label else ''}: {usd2(b.total_monthly)}",
        f"- Price {usd(b.price)}, {b.down_payment_pct:g}% down ({usd(b.down_payment)}), "
        f"{b.term_years}-year loan at {b.interest_rate:g}%",
        f"- Principal & interest {usd2(b.principal_interest)}",
        f"- Property tax {usd2(b.property_tax)}",
        f"- Insurance {usd2(b.insurance)}",
    ]
    if b.hoa:
        lines.append(f"- HOA {usd2(b.hoa)}")
    if b.pmi_applies:
        lines.append(f"- PMI {usd2(b.pmi)} (down payment under 20%)")
    return "\n".join(lines)


def scenarios_text(rows: list[PaymentBreakdown]) -> str:
    lines = [f"Monthly payment at different down payments on {usd(rows[0].price)}:"]
    lines += [
        f"- {r.down_payment_pct:g}% down ({usd(r.down_payment)}): {usd2(r.total_monthly)}/mo"
        + (" incl. PMI" if r.pmi_applies else "")
        for r in rows
    ]
    return "\n".join(lines)


def terms_text(t: TermComparison) -> str:
    s, lg = t.shorter, t.longer
    return "\n".join(
        [
            f"The {s.term_years}-year loan costs {usd2(abs(t.monthly_difference))} more per month "
            f"but saves about {usd(t.interest_saved_by_shorter)} in interest.",
            f"- {s.term_years}-year: {usd2(s.total_monthly)}/mo, "
            f"{usd(s.total_interest_over_term)} interest over the loan",
            f"- {lg.term_years}-year: {usd2(lg.total_monthly)}/mo, "
            f"{usd(lg.total_interest_over_term)} interest over the loan",
        ]
    )


def affordability_text(a: Affordability) -> str:
    if not a.affordable:
        return (
            f"Based on the debt-to-income limits, your monthly housing budget is "
            f"{usd2(a.monthly_budget)}, which does not cover the base costs of a home."
        )
    which = "front-end" if a.binding_limit == "front_end_dti" else "back-end"
    return "\n".join(
        [
            f"You could afford a home up to about {usd(a.max_home_price)}.",
            f"- Down payment {usd(a.down_payment)}, loan about {usd(a.max_loan_amount)}",
            f"- Estimated payment {usd2(a.estimated_monthly_payment or 0)}/mo",
            f"- Your {which} debt-to-income limit sets a monthly budget of "
            f"{usd2(a.monthly_budget)}",
        ]
    )


def comparison_text(c: Comparison) -> str:
    blocks = []
    for i, r in enumerate(c.listings, 1):
        pps = f"${r.price_per_sqft:,.0f}/sqft" if r.price_per_sqft else "price/sqft n/a"
        pay = usd2(r.est_monthly_payment) if r.est_monthly_payment else "n/a"
        lines = [f"{i}. {r.address}: {usd(r.price)}, {pps}, est. {pay}/mo"]
        lines += [f"+ {p}" for p in r.pros]
        lines += [f"- {x}" for x in r.cons]
        if r.missing_fields:
            lines.append(f"- Not listed: {', '.join(r.missing_fields)}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks) + f"\n{c.payment_note}"


def with_disclaimer(text: str) -> str:
    return f"{text}\n{DISCLAIMER}"
