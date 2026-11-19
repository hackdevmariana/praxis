from decimal import Decimal

from pydantic import BaseModel, Field


class BreakEvenInput(BaseModel):
    fixed_costs: Decimal = Field(ge=0)
    variable_cost_per_unit: Decimal = Field(ge=0)
    price_per_unit: Decimal = Field(gt=0)
    target_profit: Decimal = Field(default=Decimal("0"), ge=0)
    expected_units: int | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class BreakEvenOutput(BaseModel):
    contribution_margin_per_unit: Decimal
    contribution_margin_pct: Decimal
    break_even_units: int
    break_even_revenue: Decimal
    units_for_target_profit: int
    margin_of_safety_units: int | None
    margin_of_safety_pct: Decimal | None
    currency: str
