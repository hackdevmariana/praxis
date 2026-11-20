from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class RenewalCalendarInput(BaseModel):
    reference_date: date | None = None
    horizon_days: int = Field(default=90, ge=1, le=365)
    include_expired: bool = False
    category: str | None = None
    currency: str = "EUR"


class RenewalItem(BaseModel):
    contract_id: str
    supplier: str
    category: str
    renewal_date: date
    days_remaining: int
    notice_days: list[int]
    status: str
    estimated_annual_cost: Decimal | None


class RenewalCalendarOutput(BaseModel):
    reference_date: date
    horizon_end: date
    count: int
    notice_due_count: int
    next_renewal: date | None
    renewals: list[RenewalItem]
    currency: str
