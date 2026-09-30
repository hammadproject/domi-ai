"""Deterministic text for tool results and fallbacks. No LLM: every number comes from the
tools, so nothing can be invented or mis-calculated."""

from app.rag.models import Hit, RankedHit
from app.tools.compare import Comparison
from app.tools.mortgage import (
    DISCLAIMER,
    Affordability,
    PaymentBreakdown,
    TermComparison,
)

SMALLTALK_REPLY = (
    "Hi, I'm Domi. I can help you search homes for sale in Austin TX, Dallas TX and "
    "Phoenix AZ (for example '3 bed house in Austin under 500k'), estimate monthly "
    "mortgage payments, see how much house you can afford, and compare 2-3 listings. "
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
    lines = [f"{i}. {describe_hit(r.hit)}" for i, r in enumerate(ranked, 1)]
    return f"{message}\n" + "\n".join(lines)


def payment_text(b: PaymentBreakdown, label: str | None = None) -> str:
    head = f"Estimated monthly payment{f' for {label}' if label else ''}: {usd2(b.total_monthly)}"
    parts = [
        f"principal & interest {usd2(b.principal_interest)}",
        f"property tax {usd2(b.property_tax)}",
        f"insurance {usd2(b.insurance)}",
    ]
    if b.hoa:
        parts.append(f"HOA {usd2(b.hoa)}")
    if b.pmi_applies:
        parts.append(f"PMI {usd2(b.pmi)} (down payment under 20%)")
    return (
        f"{head}.\nPrice {usd(b.price)}, {b.down_payment_pct:g}% down ({usd(b.down_payment)}), "
        f"{b.term_years}-year loan at {b.interest_rate:g}%.\nBreakdown: {', '.join(parts)}."
    )


def scenarios_text(rows: list[PaymentBreakdown]) -> str:
    lines = [
        f"- {r.down_payment_pct:g}% down ({usd(r.down_payment)}): {usd2(r.total_monthly)}/mo"
        + (" incl. PMI" if r.pmi_applies else "")
        for r in rows
    ]
    return f"Monthly payment at different down payments on {usd(rows[0].price)}:\n" + "\n".join(
        lines
    )


def terms_text(t: TermComparison) -> str:
    s, lg = t.shorter, t.longer
    return (
        f"{s.term_years}-year: {usd2(s.total_monthly)}/mo (interest over the loan "
        f"{usd(s.total_interest_over_term)}).\n"
        f"{lg.term_years}-year: {usd2(lg.total_monthly)}/mo (interest over the loan "
        f"{usd(lg.total_interest_over_term)}).\n"
        f"The {s.term_years}-year loan costs {usd2(abs(t.monthly_difference))} more per month "
        f"but saves about {usd(t.interest_saved_by_shorter)} in interest."
    )


def affordability_text(a: Affordability) -> str:
    if not a.affordable:
        return (
            f"Based on the debt-to-income limits, your monthly housing budget is "
            f"{usd2(a.monthly_budget)}, which does not cover the base costs of a home."
        )
    which = "front-end" if a.binding_limit == "front_end_dti" else "back-end"
    return (
        f"With a {usd(a.down_payment)} down payment, you could afford a home up to about "
        f"{usd(a.max_home_price)} (loan about {usd(a.max_loan_amount)}), with an estimated "
        f"payment of {usd2(a.estimated_monthly_payment or 0)}/mo. Your {which} debt-to-income "
        f"limit sets a monthly budget of {usd2(a.monthly_budget)}."
    )


def comparison_text(c: Comparison) -> str:
    blocks = []
    for i, r in enumerate(c.listings, 1):
        pps = f"${r.price_per_sqft:,.0f}/sqft" if r.price_per_sqft else "price/sqft n/a"
        pay = usd2(r.est_monthly_payment) if r.est_monthly_payment else "n/a"
        lines = [f"{i}. {r.address}: {usd(r.price)}, {pps}, est. {pay}/mo"]
        lines += [f"   + {p}" for p in r.pros]
        lines += [f"   - {x}" for x in r.cons]
        if r.missing_fields:
            lines.append(f"   (not listed: {', '.join(r.missing_fields)})")
        blocks.append("\n".join(lines))
    return "\n".join(blocks) + f"\n{c.payment_note}"


def with_disclaimer(text: str) -> str:
    return f"{text}\n{DISCLAIMER}"
