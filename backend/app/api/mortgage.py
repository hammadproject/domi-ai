"""Mortgage calculator endpoints for the UI (no LLM: deterministic tool from tools/mortgage.py).

Every request may override the default assumptions (rate, property tax, insurance, PMI, DTI);
GET /api/mortgage/defaults returns the defaults so the UI never hardcodes them."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.ratelimit import limit_api
from app.tools.mortgage import (
    PMI_DOWN_PAYMENT_THRESHOLD_PCT,
    Affordability,
    MortgageAssumptions,
    PaymentBreakdown,
    TermComparison,
    affordability,
    compare_terms,
    estimate_payment,
)

router = APIRouter(dependencies=[Depends(limit_api)])


class AssumptionOverrides(BaseModel):
    interest_rate: float | None = Field(default=None, ge=0, le=30, description="annual percent")
    property_tax_rate: float | None = Field(default=None, ge=0, le=10, description="% of price/yr")
    insurance_annual: float | None = Field(default=None, ge=0, le=100_000)
    pmi_rate: float | None = Field(default=None, ge=0, le=5, description="% of loan per year")
    front_end_dti: float | None = Field(default=None, gt=0, le=1)
    back_end_dti: float | None = Field(default=None, gt=0, le=1)

    def assumptions(self) -> MortgageAssumptions:
        base = MortgageAssumptions.from_settings()
        updates = {k: v for k, v in self.model_dump().items() if v is not None}
        return base.model_copy(update=updates)


class DownPayment(BaseModel):
    down_payment: float | None = Field(default=None, ge=0)
    down_payment_pct: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def one_down_payment(self) -> "DownPayment":
        if (self.down_payment is None) == (self.down_payment_pct is None):
            raise ValueError("provide exactly one of down_payment or down_payment_pct")
        return self


class MortgageRequest(AssumptionOverrides, DownPayment):
    price: float = Field(gt=0, le=100_000_000)
    term_years: int = Field(default=30, ge=1, le=50)
    hoa_monthly: float = Field(default=0.0, ge=0, le=100_000)


class TermsRequest(AssumptionOverrides, DownPayment):
    price: float = Field(gt=0, le=100_000_000)
    hoa_monthly: float = Field(default=0.0, ge=0, le=100_000)
    short_term_years: int = Field(default=15, ge=1, le=50)
    long_term_years: int = Field(default=30, ge=1, le=50)


class AffordabilityRequest(AssumptionOverrides):
    annual_income: float = Field(gt=0, le=100_000_000)
    down_payment: float = Field(ge=0, le=100_000_000)
    monthly_debts: float = Field(default=0.0, ge=0, le=1_000_000)
    hoa_monthly: float = Field(default=0.0, ge=0, le=100_000)
    term_years: int = Field(default=30, ge=1, le=50)


class Defaults(BaseModel):
    interest_rate: float
    property_tax_rate: float
    insurance_annual: float
    pmi_rate: float
    front_end_dti: float
    back_end_dti: float
    pmi_down_payment_threshold_pct: float


@router.get("/api/mortgage/defaults", response_model=Defaults)
async def defaults() -> Defaults:
    a = MortgageAssumptions.from_settings()
    return Defaults(**a.model_dump(), pmi_down_payment_threshold_pct=PMI_DOWN_PAYMENT_THRESHOLD_PCT)


@router.post("/api/mortgage/estimate", response_model=PaymentBreakdown)
async def estimate(req: MortgageRequest) -> PaymentBreakdown:
    try:
        return estimate_payment(
            req.price,
            down_payment=req.down_payment,
            down_payment_pct=req.down_payment_pct,
            hoa_monthly=req.hoa_monthly,
            term_years=req.term_years,
            assumptions=req.assumptions(),
        )
    except ValueError as exc:  # e.g. down payment larger than the price
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/mortgage/compare-terms", response_model=TermComparison)
async def terms(req: TermsRequest) -> TermComparison:
    if req.short_term_years == req.long_term_years:
        raise HTTPException(status_code=422, detail="the two loan terms must differ")
    try:
        return compare_terms(
            req.price,
            down_payment=req.down_payment,
            down_payment_pct=req.down_payment_pct,
            hoa_monthly=req.hoa_monthly,
            terms=(req.short_term_years, req.long_term_years),
            assumptions=req.assumptions(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/mortgage/affordability", response_model=Affordability)
async def how_much(req: AffordabilityRequest) -> Affordability:
    try:
        return affordability(
            annual_income=req.annual_income,
            down_payment=req.down_payment,
            monthly_debts=req.monthly_debts,
            hoa_monthly=req.hoa_monthly,
            term_years=req.term_years,
            assumptions=req.assumptions(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
