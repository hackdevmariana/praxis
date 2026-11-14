from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from app.tools.datetime.business_days.schemas import HolidayApplied


class Period(StrEnum):
    month = "month"
    quarter = "quarter"
    year = "year"


class DeadlineInput(BaseModel):
    period: Period
    reference_date: date | None = None
    timezone: str = "Europe/Madrid"
    community: str | None = None
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")


class DeadlineOutput(BaseModel):
    period: Period
    period_start: date
    deadline: date
    days_remaining: int
    business_days_remaining: int
    holidays_applied: list[HolidayApplied]
