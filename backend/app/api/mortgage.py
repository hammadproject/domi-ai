"""POST /api/mortgage/estimate: direct calculator endpoint for UI use (no LLM)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.ratelimit import limit_api
from app.tools.mortgage import MortgageAssumptions, PaymentBreakdown, estimate_payment

router = APIRouter(dependencies=[Depends(limit_api)])


class MortgageRequest(BaseModel):
    price: float = Field(gt=0, le=100_000_000)
    down_payment: float | None = Field(default=None, ge=0)
    down_payment_pct: float | None = Field(default=None, ge=0, le=100)
    term_years: int = Field(default=30, ge=1, le=50)
    hoa_monthly: float = Field(default=0.0, ge=0, le=100_000)
    interest_rate: float | None = Field(default=None, ge=0, le=30, description="annual percent")

    @model_validator(mode="after")
    def one_down_payment(self) -> "MortgageRequest":
        if (self.down_payment is None) == (self.down_payment_pct is None):
            raise ValueError("provide exactly one of down_payment or down_payment_pct")
        return self


@router.post("/api/mortgage/estimate", response_model=PaymentBreakdown)
async def estimate(req: MortgageRequest) -> PaymentBreakdown:
    try:
        return estimate_payment(
            req.price,
            down_payment=req.down_payment,
            down_payment_pct=req.down_payment_pct,
            hoa_monthly=req.hoa_monthly,
            term_years=req.term_years,
            assumptions=MortgageAssumptions.from_settings(),
            interest_rate=req.interest_rate,
        )
    except ValueError as exc:  # e.g. down payment larger than the price
        raise HTTPException(status_code=422, detail=str(exc)) from exc
