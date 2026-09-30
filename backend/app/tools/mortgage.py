"""US mortgage / affordability estimates. Pure, deterministic Python (never LLM math).

All results are ESTIMATES built on configurable assumptions, not a loan offer.
"""

from pydantic import BaseModel, Field

from app.config import get_settings

DISCLAIMER = (
    "Estimate only, based on the assumptions shown (rate, property tax, insurance, PMI). "
    "Not a loan offer or a commitment to lend."
)
PMI_DOWN_PAYMENT_THRESHOLD_PCT = 20.0


class MortgageAssumptions(BaseModel):
    interest_rate: float = Field(ge=0, description="annual percent, e.g. 6.75")
    property_tax_rate: float = Field(ge=0, description="percent of price per year")
    insurance_annual: float = Field(ge=0, description="homeowners insurance, $/year")
    pmi_rate: float = Field(ge=0, description="percent of loan per year, when PMI applies")
    front_end_dti: float = Field(default=0.28, gt=0, le=1)
    back_end_dti: float = Field(default=0.36, gt=0, le=1)

    @classmethod
    def from_settings(cls) -> "MortgageAssumptions":
        s = get_settings()
        return cls(
            interest_rate=s.default_interest_rate,
            property_tax_rate=s.property_tax_rate_default,
            insurance_annual=s.home_insurance_annual_default,
            pmi_rate=s.pmi_rate_default,
            front_end_dti=s.front_end_dti,
            back_end_dti=s.back_end_dti,
        )


class PaymentBreakdown(BaseModel):
    price: float
    down_payment: float
    down_payment_pct: float
    loan_amount: float
    term_years: int
    interest_rate: float
    principal_interest: float
    property_tax: float
    insurance: float
    hoa: float
    pmi: float
    pmi_applies: bool
    total_monthly: float
    total_interest_over_term: float
    assumptions_note: str = DISCLAIMER


def monthly_principal_interest(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard amortization: P * i / (1 - (1+i)^-n); straight division at 0% interest."""
    if principal < 0 or years <= 0 or annual_rate_pct < 0:
        raise ValueError("principal >= 0, years > 0 and rate >= 0 are required")
    n = years * 12
    i = annual_rate_pct / 1200
    if principal == 0:
        return 0.0
    if i == 0:
        return principal / n
    return principal * i / (1 - (1 + i) ** -n)


def _monthly_costs(
    price: float, down: float, hoa: float, years: int, a: MortgageAssumptions, rate: float
) -> tuple[float, float, float, float, float, bool]:
    """(pi, tax, insurance, hoa, pmi, pmi_applies) for a price/down combination."""
    loan = price - down
    pi = monthly_principal_interest(loan, rate, years)
    tax = price * a.property_tax_rate / 100 / 12
    ins = a.insurance_annual / 12
    pmi_applies = price > 0 and (down / price * 100) < PMI_DOWN_PAYMENT_THRESHOLD_PCT
    pmi = loan * a.pmi_rate / 100 / 12 if pmi_applies else 0.0
    return pi, tax, ins, hoa, pmi, pmi_applies


def estimate_payment(
    price: float,
    *,
    down_payment: float | None = None,
    down_payment_pct: float | None = None,
    hoa_monthly: float = 0.0,
    term_years: int = 30,
    assumptions: MortgageAssumptions | None = None,
    interest_rate: float | None = None,
) -> PaymentBreakdown:
    """Full monthly payment: P&I + property tax + insurance + HOA + PMI (if down < 20%)."""
    a = assumptions or MortgageAssumptions.from_settings()
    if price <= 0:
        raise ValueError("price must be positive")
    if (down_payment is None) == (down_payment_pct is None):
        raise ValueError("give exactly one of down_payment or down_payment_pct")
    down = down_payment if down_payment is not None else price * down_payment_pct / 100  # type: ignore[operator]
    if not 0 <= down <= price:
        raise ValueError("down payment must be between 0 and the price")
    if hoa_monthly < 0:
        raise ValueError("hoa_monthly cannot be negative")

    rate = a.interest_rate if interest_rate is None else interest_rate
    pi, tax, ins, hoa, pmi, pmi_applies = _monthly_costs(
        price, down, hoa_monthly, term_years, a, rate
    )
    total = pi + tax + ins + hoa + pmi
    return PaymentBreakdown(
        price=round(price, 2),
        down_payment=round(down, 2),
        down_payment_pct=round(down / price * 100, 2),
        loan_amount=round(price - down, 2),
        term_years=term_years,
        interest_rate=rate,
        principal_interest=round(pi, 2),
        property_tax=round(tax, 2),
        insurance=round(ins, 2),
        hoa=round(hoa, 2),
        pmi=round(pmi, 2),
        pmi_applies=pmi_applies,
        total_monthly=round(total, 2),
        total_interest_over_term=round(pi * term_years * 12 - (price - down), 2),
    )


def down_payment_scenarios(
    price: float,
    pcts: tuple[float, ...] = (0, 5, 10, 20),
    *,
    hoa_monthly: float = 0.0,
    term_years: int = 30,
    assumptions: MortgageAssumptions | None = None,
) -> list[PaymentBreakdown]:
    return [
        estimate_payment(
            price,
            down_payment_pct=p,
            hoa_monthly=hoa_monthly,
            term_years=term_years,
            assumptions=assumptions,
        )
        for p in pcts
    ]


class TermComparison(BaseModel):
    shorter: PaymentBreakdown
    longer: PaymentBreakdown
    monthly_difference: float  # shorter - longer (positive: shorter term costs more per month)
    interest_saved_by_shorter: float


def compare_terms(
    price: float,
    *,
    down_payment: float | None = None,
    down_payment_pct: float | None = None,
    hoa_monthly: float = 0.0,
    terms: tuple[int, int] = (15, 30),
    rates: dict[int, float] | None = None,
    assumptions: MortgageAssumptions | None = None,
) -> TermComparison:
    """15 vs 30 year (or any two terms). `rates` optionally sets a different rate per term."""
    short, long_ = sorted(terms)
    rates = rates or {}
    kw = {
        "down_payment": down_payment,
        "down_payment_pct": down_payment_pct,
        "hoa_monthly": hoa_monthly,
        "assumptions": assumptions,
    }
    s = estimate_payment(price, term_years=short, interest_rate=rates.get(short), **kw)
    lg = estimate_payment(price, term_years=long_, interest_rate=rates.get(long_), **kw)
    return TermComparison(
        shorter=s,
        longer=lg,
        monthly_difference=round(s.total_monthly - lg.total_monthly, 2),
        interest_saved_by_shorter=round(
            lg.total_interest_over_term - s.total_interest_over_term, 2
        ),
    )


class Affordability(BaseModel):
    affordable: bool
    max_home_price: float | None
    max_loan_amount: float | None
    estimated_monthly_payment: float | None
    monthly_budget: float
    binding_limit: str  # "front_end_dti" or "back_end_dti"
    down_payment: float
    note: str = DISCLAIMER


def affordability(
    *,
    annual_income: float,
    down_payment: float,
    monthly_debts: float = 0.0,
    hoa_monthly: float = 0.0,
    term_years: int = 30,
    assumptions: MortgageAssumptions | None = None,
) -> Affordability:
    """Highest price whose full monthly payment fits both DTI limits.

    Budget = min(front_end_dti * income, back_end_dti * income - other debts), monthly.
    The payment is non-decreasing in price, so we bisect for the largest price that fits.
    """
    a = assumptions or MortgageAssumptions.from_settings()
    if annual_income <= 0 or down_payment < 0 or monthly_debts < 0 or hoa_monthly < 0:
        raise ValueError("income must be positive; down payment, debts and HOA cannot be negative")

    monthly_income = annual_income / 12
    front = a.front_end_dti * monthly_income
    back = a.back_end_dti * monthly_income - monthly_debts
    budget, binding = (front, "front_end_dti") if front <= back else (back, "back_end_dti")
    budget = max(budget, 0.0)

    def payment(price: float) -> float:
        down = min(down_payment, price)
        return sum(_monthly_costs(price, down, hoa_monthly, term_years, a, a.interest_rate)[:5])

    def result(price: float | None) -> Affordability:
        if price is None:
            return Affordability(
                affordable=False, max_home_price=None, max_loan_amount=None,
                estimated_monthly_payment=None, monthly_budget=round(budget, 2),
                binding_limit=binding, down_payment=down_payment,
            )  # fmt: skip
        return Affordability(
            affordable=True,
            max_home_price=round(price, 2),
            max_loan_amount=round(max(price - down_payment, 0), 2),
            estimated_monthly_payment=round(payment(price), 2),
            monthly_budget=round(budget, 2),
            binding_limit=binding,
            down_payment=down_payment,
        )

    lo = 0.0  # a price of 0 costs only insurance + HOA; require at least that to fit
    if budget <= 0 or payment(1.0) > budget:
        return result(None)
    hi = max(down_payment, 1.0) * 100 + annual_income * 50
    for _ in range(100):
        mid = (lo + hi) / 2
        if payment(mid) <= budget:
            lo = mid
        else:
            hi = mid
    return result(lo)
