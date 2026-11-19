from decimal import Decimal

from pydantic import BaseModel, Field


class BusinessKpiInput(BaseModel):
    revenue: Decimal = Field(ge=0)
    cogs: Decimal = Field(ge=0)
    operating_expenses: Decimal = Field(ge=0)
    depreciation_amortization: Decimal = Field(default=Decimal("0"), ge=0)
    receivables: Decimal = Field(default=Decimal("0"), ge=0)
    payables: Decimal = Field(default=Decimal("0"), ge=0)
    inventory: Decimal = Field(default=Decimal("0"), ge=0)
    cash: Decimal = Field(default=Decimal("0"), ge=0)
    current_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    period_days: int = Field(default=365, ge=30, le=366)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class BusinessKpiOutput(BaseModel):
    gross_profit: Decimal
    gross_margin_pct: Decimal | None
    ebit: Decimal
    ebit_margin_pct: Decimal | None
    ebitda: Decimal
    dso_days: Decimal | None
    dpo_days: Decimal | None
    dio_days: Decimal | None
    cash_conversion_cycle_days: Decimal | None
    current_ratio: Decimal | None
    working_capital: Decimal
    currency: str
