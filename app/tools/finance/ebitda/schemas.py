from decimal import Decimal

from pydantic import BaseModel, Field


class EbitdaInput(BaseModel):
    revenue: Decimal = Field(ge=0)
    cogs: Decimal = Field(ge=0)
    operating_expenses: Decimal = Field(ge=0)
    depreciation_amortization: Decimal = Field(default=Decimal("0"), ge=0)
    non_recurring_income: Decimal = Field(default=Decimal("0"), ge=0)
    non_recurring_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class EbitdaOutput(BaseModel):
    ebitda: Decimal
    adjusted_ebitda: Decimal
    ebit: Decimal
    ebitda_margin_pct: Decimal | None
    adjusted_ebitda_margin_pct: Decimal | None
    ebit_margin_pct: Decimal | None
    currency: str
