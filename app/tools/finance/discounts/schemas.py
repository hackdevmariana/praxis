from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class DiscountOperation(StrEnum):
    apply = "apply"
    reverse = "reverse"


class DiscountsInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    discounts: list[Annotated[Decimal, Field(ge=0, le=100)]] = Field(min_length=1, max_length=10)
    operation: DiscountOperation = DiscountOperation.apply
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class DiscountsOutput(BaseModel):
    original_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal
    effective_discount_pct: Decimal
    currency: str
