from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class VatOperation(StrEnum):
    add = "add"
    extract = "extract"
    remove = "remove"


class VatInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    operation: VatOperation = VatOperation.add
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class VatOutput(BaseModel):
    base_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    currency: str
