from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, model_validator


class SavingsCategory(StrEnum):
    tpv = "tpv"
    supplies = "supplies"
    energy = "energy"
    other = "other"


class SavingsStatus(StrEnum):
    realized = "realized"
    projected = "projected"
    all = "all"


class SavingsLedgerInput(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    category: SavingsCategory | None = None
    status: SavingsStatus = SavingsStatus.all
    currency: str = "EUR"

    @model_validator(mode="after")
    def periodo(self) -> "SavingsLedgerInput":
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("Aporta period_start y period_end juntos")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start no puede ser posterior a period_end")
        return self


class SavingsEntry(BaseModel):
    id: str
    date: date
    category: SavingsCategory
    supplier: str | None
    description: str
    baseline_cost: Decimal
    actual_cost: Decimal
    savings: Decimal
    annualized_savings: Decimal
    status: str


class CategoryTotal(BaseModel):
    category: SavingsCategory
    savings: Decimal
    annualized_savings: Decimal
    count: int


class SavingsLedgerOutput(BaseModel):
    period_start: date
    period_end: date
    entries: list[SavingsEntry]
    total_savings: Decimal
    total_annualized: Decimal
    by_category: list[CategoryTotal]
    count: int
    currency: str
