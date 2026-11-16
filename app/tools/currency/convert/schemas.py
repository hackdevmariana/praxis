from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, Field


class CurrencyConvertInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    date: Date | None = None


class CurrencyConvertOutput(BaseModel):
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    rate_date: Date
    from_currency: str
    to_currency: str
