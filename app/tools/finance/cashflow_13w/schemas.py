from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Cashflow13wInput(BaseModel):
    opening_balance: Decimal
    weekly_inflows: list[Decimal] = Field(min_length=13, max_length=13)
    weekly_outflows: list[Decimal] = Field(min_length=13, max_length=13)
    start_date: date | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @field_validator("weekly_inflows", "weekly_outflows")
    @classmethod
    def no_negativos(cls, value: list[Decimal]) -> list[Decimal]:
        if any(amount < 0 for amount in value):
            raise ValueError("Los importes semanales no pueden ser negativos")
        return value


class CashflowWeek(BaseModel):
    week: int
    week_start: date | None
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    closing_balance: Decimal


class Cashflow13wOutput(BaseModel):
    opening_balance: Decimal
    weeks: list[CashflowWeek]
    end_balance: Decimal
    min_balance: Decimal
    min_week: int
    weeks_with_negative_balance: int
    currency: str
