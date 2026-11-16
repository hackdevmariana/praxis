from decimal import Decimal

from pydantic import BaseModel, Field


class TpvSavingsInput(BaseModel):
    annual_card_turnover: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    current_rate_pct: Decimal = Field(ge=0, le=100)
    new_rate_pct: Decimal = Field(ge=0, le=100)
    average_ticket: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class TpvSavingsOutput(BaseModel):
    current_cost: Decimal
    new_cost: Decimal
    annual_savings: Decimal
    monthly_savings: Decimal
    savings_pct: Decimal | None
    savings_per_ticket: Decimal | None
    currency: str
