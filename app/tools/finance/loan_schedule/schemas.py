from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class LoanType(StrEnum):
    french = "french"
    italian = "italian"


class LoanInput(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    annual_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    term_months: int = Field(gt=0, le=600)
    type: LoanType = LoanType.french
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class Installment(BaseModel):
    period: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


class LoanOutput(BaseModel):
    principal: Decimal
    annual_rate: Decimal
    term_months: int
    type: LoanType
    monthly_payment: Decimal | None
    first_payment: Decimal
    last_payment: Decimal
    total_interest: Decimal
    total_paid: Decimal
    schedule: list[Installment]
    currency: str
