import pytest

from app.rag.models import Hit
from app.tools.compare import compare_listings
from app.tools.mortgage import (
    MortgageAssumptions,
    affordability,
    compare_terms,
    down_payment_scenarios,
    estimate_payment,
    monthly_principal_interest,
)

# Clean round numbers so expected values are easy to verify by hand.
A = MortgageAssumptions(
    interest_rate=6.0, property_tax_rate=1.2, insurance_annual=1200, pmi_rate=0.6
)


# ---------- principal & interest: known published values ----------
@pytest.mark.parametrize(
    "principal,rate,years,expected",
    [
        (300_000, 6.5, 30, 1896.20),
        (200_000, 4.0, 30, 954.83),
        (200_000, 4.0, 15, 1479.38),
        (400_000, 7.0, 30, 2661.21),
        (100_000, 0.0, 10, 833.33),  # 0% interest: straight division
    ],
)
def test_principal_interest_known_examples(principal, rate, years, expected) -> None:
    assert monthly_principal_interest(principal, rate, years) == pytest.approx(expected, abs=0.01)


def test_zero_principal_and_invalid_inputs() -> None:
    assert monthly_principal_interest(0, 6.5, 30) == 0.0
    for bad in [(-1, 6, 30), (1000, -1, 30), (1000, 6, 0)]:
        with pytest.raises(ValueError):
            monthly_principal_interest(*bad)


# ---------- full payment ----------
def test_payment_components_20_percent_down_no_pmi() -> None:
    r = estimate_payment(500_000, down_payment_pct=20, hoa_monthly=100, assumptions=A)
    assert r.loan_amount == 400_000 and r.down_payment == 100_000
    assert r.principal_interest == pytest.approx(2398.20, abs=0.01)  # $400k @ 6% / 30y
    assert r.property_tax == 500.00  # 500k * 1.2% / 12
    assert r.insurance == 100.00
    assert r.hoa == 100.00
    assert r.pmi == 0 and not r.pmi_applies
    assert r.total_monthly == pytest.approx(2398.20 + 500 + 100 + 100, abs=0.02)


def test_pmi_applies_only_below_20_percent_down() -> None:
    at_threshold = estimate_payment(500_000, down_payment_pct=20, assumptions=A)
    just_below = estimate_payment(500_000, down_payment=99_999, assumptions=A)
    assert not at_threshold.pmi_applies and at_threshold.pmi == 0
    assert just_below.pmi_applies
    assert just_below.pmi == pytest.approx(400_001 * 0.6 / 100 / 12, abs=0.01)


def test_zero_down_payment() -> None:
    r = estimate_payment(300_000, down_payment=0, assumptions=A)
    assert r.loan_amount == 300_000 and r.down_payment_pct == 0
    assert r.pmi_applies and r.pmi == pytest.approx(150.00)  # 300k * 0.6% / 12
    assert r.principal_interest == pytest.approx(1798.65, abs=0.01)


def test_all_cash_no_loan() -> None:
    r = estimate_payment(300_000, down_payment_pct=100, assumptions=A)
    assert r.loan_amount == 0 and r.principal_interest == 0 and r.pmi == 0
    assert r.total_monthly == pytest.approx(300 + 100)  # tax + insurance only


def test_zero_hoa_default() -> None:
    r = estimate_payment(400_000, down_payment_pct=20, assumptions=A)
    assert r.hoa == 0
    assert r.total_monthly == pytest.approx(
        r.principal_interest + r.property_tax + r.insurance, abs=0.02
    )


def test_zero_percent_interest_rate() -> None:
    zero = MortgageAssumptions(interest_rate=0, property_tax_rate=0, insurance_annual=0, pmi_rate=0)
    r = estimate_payment(360_000, down_payment_pct=0, assumptions=zero)
    assert r.principal_interest == 1000.00 and r.total_monthly == 1000.00
    assert r.total_interest_over_term == 0


def test_total_interest_over_term() -> None:
    r = estimate_payment(300_000, down_payment_pct=0, assumptions=A)
    assert r.total_interest_over_term == pytest.approx(1798.65 * 360 - 300_000, abs=5)


def test_estimate_payment_validation() -> None:
    with pytest.raises(ValueError):
        estimate_payment(0, down_payment_pct=10, assumptions=A)
    with pytest.raises(ValueError):
        estimate_payment(300_000, assumptions=A)  # neither down payment given
    with pytest.raises(ValueError):
        estimate_payment(300_000, down_payment=1, down_payment_pct=1, assumptions=A)  # both
    with pytest.raises(ValueError):
        estimate_payment(300_000, down_payment=400_000, assumptions=A)
    with pytest.raises(ValueError):
        estimate_payment(300_000, down_payment_pct=10, hoa_monthly=-5, assumptions=A)


def test_disclaimer_is_always_present() -> None:
    r = estimate_payment(300_000, down_payment_pct=10, assumptions=A)
    assert "not a loan offer" in r.assumptions_note.lower()


# ---------- scenarios & term comparison ----------
def test_down_payment_scenarios_payment_falls_as_down_payment_rises() -> None:
    rows = down_payment_scenarios(400_000, assumptions=A)
    assert [r.down_payment_pct for r in rows] == [0, 5, 10, 20]
    totals = [r.total_monthly for r in rows]
    assert totals == sorted(totals, reverse=True)
    assert [r.pmi_applies for r in rows] == [True, True, True, False]


def test_15_vs_30_year() -> None:
    cmp = compare_terms(200_000, down_payment_pct=20, terms=(30, 15), assumptions=A)
    assert cmp.shorter.term_years == 15 and cmp.longer.term_years == 30
    assert cmp.monthly_difference > 0  # shorter term costs more per month
    assert cmp.interest_saved_by_shorter > 0
    assert cmp.interest_saved_by_shorter == pytest.approx(
        cmp.longer.total_interest_over_term - cmp.shorter.total_interest_over_term, abs=0.01
    )


def test_term_comparison_with_per_term_rates() -> None:
    cmp = compare_terms(200_000, down_payment_pct=20, rates={15: 5.0, 30: 6.0}, assumptions=A)
    assert cmp.shorter.interest_rate == 5.0 and cmp.longer.interest_rate == 6.0


# ---------- affordability ----------
def test_affordability_respects_both_dti_limits_and_is_self_consistent() -> None:
    r = affordability(annual_income=120_000, monthly_debts=500, down_payment=60_000, assumptions=A)
    # front: 0.28 * 10,000 = 2,800 ; back: 0.36 * 10,000 - 500 = 3,100 -> front binds
    assert r.monthly_budget == 2800.00 and r.binding_limit == "front_end_dti"
    assert r.affordable and r.max_home_price
    assert r.estimated_monthly_payment <= 2800.00 + 0.01
    # the payment at that price really fits, and a noticeably higher price does not
    at = estimate_payment(r.max_home_price, down_payment=60_000, assumptions=A)
    assert at.total_monthly <= 2800.01
    above = estimate_payment(r.max_home_price + 5_000, down_payment=60_000, assumptions=A)
    assert above.total_monthly > 2800.00


def test_affordability_back_end_binds_with_heavy_debt() -> None:
    r = affordability(
        annual_income=120_000, monthly_debts=1_500, down_payment=60_000, assumptions=A
    )
    assert r.binding_limit == "back_end_dti" and r.monthly_budget == 2100.00


def test_affordability_more_debt_means_lower_price() -> None:
    lo = affordability(annual_income=100_000, monthly_debts=0, down_payment=40_000, assumptions=A)
    hi = affordability(
        annual_income=100_000, monthly_debts=1_200, down_payment=40_000, assumptions=A
    )
    assert hi.max_home_price < lo.max_home_price


def test_affordability_not_affordable_when_debts_exceed_budget() -> None:
    r = affordability(annual_income=60_000, monthly_debts=2_000, down_payment=10_000, assumptions=A)
    assert not r.affordable and r.max_home_price is None and r.monthly_budget == 0


def test_affordability_input_validation() -> None:
    with pytest.raises(ValueError):
        affordability(annual_income=0, down_payment=0, assumptions=A)
    with pytest.raises(ValueError):
        affordability(annual_income=50_000, down_payment=-1, assumptions=A)


# ---------- listing comparison ----------
def listing(i: str, price, sqft, beds, baths, year, hoa=None) -> Hit:
    return Hit(
        id=i, address=f"{i} Main St", city="Austin", state="TX", price=price, sqft=sqft,
        beds=beds, baths=baths, year_built=year, hoa_fee=hoa,
    )  # fmt: skip


def test_compare_two_listings_pros_cons_from_fields() -> None:
    a = listing("a", 400_000, 2_000, 3, 2, 2010, hoa=100)
    b = listing("b", 500_000, 2_500, 4, 3, 1995, hoa=300)
    res = compare_listings([a, b], assumptions=A)
    ra, rb = res.listings
    assert ra.price_per_sqft == 200.0 and rb.price_per_sqft == 200.0
    assert any("Lowest list price" in p for p in ra.pros)
    assert any("Newest build" in p for p in ra.pros)
    assert any("Lowest HOA" in p for p in ra.pros)
    assert any("Most living space" in p for p in rb.pros)
    assert any("Highest list price" in c for c in rb.cons)
    assert ra.est_monthly_payment < rb.est_monthly_payment
    # equal price/sqft -> no claim either way
    assert not any("price per sqft" in s for s in ra.pros + ra.cons + rb.pros + rb.cons)
    assert "20% down" in res.payment_note and "not a loan offer" in res.payment_note.lower()


def test_compare_three_and_missing_fields_make_no_claims() -> None:
    a = listing("a", 300_000, None, None, None, None)
    b = listing("b", 350_000, 1_500, 3, 2, 2000)
    c = listing("c", 320_000, 1_400, 3, 2, 2005)
    res = compare_listings([a, b, c], assumptions=A)
    ra = res.listings[0]
    assert ra.price_per_sqft is None
    assert set(ra.missing_fields) == {"beds", "baths", "sqft", "year_built"}
    assert any("Lowest list price" in p for p in ra.pros)
    # a has no sqft, so only b and c are compared on space / price per sqft
    assert not any("living space" in s for s in ra.pros + ra.cons)
    assert any("Most living space" in p for p in res.listings[1].pros)


def test_missing_hoa_is_never_called_lowest_hoa() -> None:
    a = listing("a", 300_000, 1_500, 3, 2, 2000, hoa=None)
    b = listing("b", 310_000, 1_500, 3, 2, 2000, hoa=250)
    c = listing("c", 320_000, 1_500, 3, 2, 2000, hoa=50)
    res = compare_listings([a, b, c], assumptions=A)
    assert not any("HOA" in s for s in res.listings[0].pros + res.listings[0].cons)
    assert any("Lowest HOA" in p for p in res.listings[2].pros)


def test_compare_requires_two_or_three() -> None:
    one = [listing("a", 1, 1, 1, 1, 2000)]
    with pytest.raises(ValueError):
        compare_listings(one, assumptions=A)
    with pytest.raises(ValueError):
        compare_listings(one * 4, assumptions=A)


def test_compare_language_has_no_subjective_neighborhood_claims() -> None:
    a = listing("a", 400_000, 2_000, 3, 2, 2010, hoa=100)
    b = listing("b", 500_000, 2_500, 4, 3, 1995, hoa=300)
    res = compare_listings([a, b], assumptions=A)
    text = " ".join(s for r in res.listings for s in r.pros + r.cons).lower()
    for banned in ("safe", "family-friendly", "good school", "quiet", "desirable", "up-and-coming"):
        assert banned not in text
